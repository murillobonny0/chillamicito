import assert from 'node:assert/strict';
import { test } from 'node:test';
import { createOperation, createStockClient, normalizeLegacySnapshot, projectSnapshot } from '../src/stockOffline.js';
import { createAuthSession } from '../src/authSession.js';

const user = { id_usuario: 7, username: 'operador', rol: 'ayudante_cocina' };
const snapshot = () => ({ insumos: [{ id_insumo: 1, nombre: 'Papa', cantidad_actual: 10, stock_minimo: 5 }], entradas: [], salidas: [], mermas: [] });
const payload = (cantidad = 2) => ({ detalles: [{ id_insumo: 1, cantidad, costo_unitario: 1 }] });

function setup() {
  let token = 'token';
  Object.defineProperty(globalThis, 'navigator', { configurable: true, value: { onLine: true } });
  globalThis.sessionStorage = { getItem: () => token };
  let data = snapshot();
  const queue = new Map();
  const accepted = new Map();
  let requests = 0;
  let unavailable = false;
  let reject = false;
  let loseResponse = false;
  const networkError = () => Object.assign(new Error('Sin conexion'), { isAxiosError: true });
  const storage = {
    getSnapshot: async () => structuredClone(data),
    mergeSnapshot: async (_user, changes) => { data = { ...data, ...structuredClone(changes) }; },
    listOperations: async () => structuredClone([...queue.values()].sort((a, b) => a.sequence - b.sequence)),
    addOperation: async (operation) => { queue.set(operation.id, structuredClone(operation)); },
    removeOperation: async (id) => { queue.delete(id); },
    reconcileSnapshot: async (_user, next, operations) => {
      data = structuredClone(next);
      operations.forEach((operation) => queue.delete(operation.id));
    },
  };
  const api = {
    post: async (endpoint, body) => {
      requests++;
      if (reject) throw Object.assign(new Error('Stock insuficiente'), { response: { status: 400, data: { detalles: ['Stock insuficiente'] } } });
      if (!accepted.has(body.id_operacion)) accepted.set(body.id_operacion, { ...body, endpoint });
      if (loseResponse) { loseResponse = false; throw networkError(); }
      return { data: body };
    },
    get: async (endpoint) => {
      if (unavailable) throw networkError();
      const kind = endpoint.split('/').at(-2);
      if (kind === 'catalogos') return { data: { categorias: [], unidades: [] } };
      if (kind === 'insumos') {
        const delta = [...accepted.values()].reduce((sum, item) => sum + item.detalles[0].cantidad * (item.endpoint.includes('entradas') ? 1 : -1), 0);
        return { data: [{ ...snapshot().insumos[0], cantidad_actual: 10 + delta }] };
      }
      return { data: [] };
    },
  };
  return {
    client: createStockClient(api, storage), storage, api, queue, accepted,
    requests: () => requests,
    disconnect: () => { navigator.onLine = false; },
    reconnect: () => { navigator.onLine = true; },
    loseResponse: () => { loseResponse = true; },
    failReads: (value) => { unavailable = value; },
    reject: (value) => { reject = value; },
    switchSession: () => { token = 'other-token'; },
  };
}

test('entradas, salidas y mermas se reflejan sin modificar la base', () => {
  const data = snapshot();
  const entrada = createOperation(user, 'entrada', payload(3), data.insumos);
  const salida = createOperation(user, 'salida', payload(2), data.insumos);
  const merma = createOperation(user, 'merma', { id_insumo: 1, cantidad: 1, motivo: 'Recorte' }, data.insumos);
  assert.equal(projectSnapshot(data, [entrada, salida, merma]).insumos[0].cantidad_actual, 10);
  assert.equal(data.insumos[0].cantidad_actual, 10);
  assert.equal(projectSnapshot(data, [entrada]).entradas.length, 1);
});

test('validacion conserva minimo y rechaza cantidades invalidas', () => {
  for (const quantity of [0, -1, NaN, Infinity]) assert.throws(() => createOperation(user, 'salida', payload(quantity), snapshot().insumos));
  assert.throws(() => createOperation(user, 'salida', payload(6), snapshot().insumos));
  assert.doesNotThrow(() => createOperation(user, 'salida', payload(5), snapshot().insumos));
  assert.throws(() => createOperation(user, 'merma', { id_insumo: 1, cantidad: 11, motivo: 'Recorte' }, snapshot().insumos));
});

test('valida el consumo acumulado de detalles del mismo insumo', () => {
  assert.throws(() => createOperation(user, 'salida', { detalles: [{ id_insumo: 1, cantidad: 3 }, { id_insumo: 1, cantidad: 3 }] }, snapshot().insumos));
});

test('offline persiste, recarga y sincroniza en orden al reconectar', async () => {
  const env = setup();
  env.disconnect();
  await env.client.save(user, 'token', 'entrada', payload(3));
  const saved = await env.client.save(user, 'token', 'salida', payload(4));
  assert.equal(saved.data.insumos[0].cantidad_actual, 9);
  assert.equal(env.requests(), 0);
  assert.equal((await env.client.cached(user)).data.salidas.length, 1);
  env.reconnect();
  const synced = await env.client.sync(user, 'token');
  assert.equal(synced.operations.length, 0);
  assert.equal(synced.data.insumos[0].cantidad_actual, 9);
  assert.equal(env.accepted.size, 2);
});

test('respuesta perdida reutiliza el ID y no duplica stock', async () => {
  const env = setup();
  env.loseResponse();
  await env.client.save(user, 'token', 'entrada', payload());
  const synced = await env.client.sync(user, 'token');
  assert.equal(env.requests(), 2);
  assert.equal(env.accepted.size, 1);
  assert.equal(synced.data.insumos[0].cantidad_actual, 12);
});

test('fallo de lectura tras POST no vuelve a enviar el movimiento', async () => {
  const env = setup();
  env.failReads(true);
  const saved = await env.client.save(user, 'token', 'entrada', payload());
  assert.equal(saved.operations[0].status, 'synced');
  assert.equal(saved.data.insumos[0].cantidad_actual, 12);
  env.failReads(false);
  await env.client.sync(user, 'token');
  assert.equal(env.requests(), 1);
});

test('rechazo detiene la cola y permite revisar o reintentar', async () => {
  const env = setup();
  env.disconnect();
  await env.client.save(user, 'token', 'entrada', payload());
  await env.client.save(user, 'token', 'salida', payload());
  env.reconnect();
  env.reject(true);
  const failed = await env.client.sync(user, 'token');
  assert.equal(failed.operations[0].status, 'error');
  assert.equal(failed.data.insumos[0].cantidad_actual, 8);
  assert.equal(env.requests(), 1);
  await env.client.sync(user, 'token');
  assert.equal(env.requests(), 1);
  env.reject(false);
  const synced = await env.client.sync(user, 'token', true);
  assert.equal(synced.operations.length, 0);
});

test('no envia con la credencial de otra sesion', async () => {
  const env = setup();
  env.disconnect();
  await env.client.save(user, 'token', 'entrada', payload());
  env.switchSession();
  env.reconnect();
  await env.client.sync(user, 'token');
  assert.equal(env.requests(), 0);
});

test('dos usuarios sincronizan sus pendientes con su propia credencial y cache', async () => {
  setup();
  navigator.onLine = false;
  const otherUser = { ...user, id_usuario: 8, username: 'otro-operador' };
  const snapshots = new Map([[7, { ...snapshot(), offlineVersion: 2 }], [8, { ...snapshot(), offlineVersion: 2 }]]);
  const operations = new Map();
  const storage = {
    getSnapshot: async (id) => structuredClone(snapshots.get(id)),
    listOperations: async (id) => structuredClone([...operations.values()].filter((item) => item.userId === String(id))),
    addOperation: async (item) => { operations.set(item.id, structuredClone(item)); },
    reconcileSnapshot: async (id, data, confirmed) => {
      snapshots.set(id, structuredClone(data));
      confirmed.forEach((item) => operations.delete(item.id));
    },
  };
  const sessions = [7, 8].map((id, index) => {
    const values = new Map();
    const session = createAuthSession({
      getItem: (key) => values.get(key) ?? null,
      setItem: (key, value) => values.set(key, value),
      removeItem: (key) => values.delete(key),
    });
    session.save(`token-${id}`, index === 0 ? user : otherUser);
    return session;
  });
  const sent = [];
  const api = {
    post: async (_endpoint, body, config) => { sent.push({ id: body.id_operacion, token: config.headers.Authorization }); },
    get: async (endpoint) => ({ data: endpoint.endsWith('/insumos/') ? snapshot().insumos : [] }),
  };
  const first = createStockClient(api, storage, sessions[0]);
  const second = createStockClient(api, storage, sessions[1]);
  await first.save(user, 'token-7', 'entrada', payload(1));
  await second.save(otherUser, 'token-8', 'salida', payload(2));
  assert.equal((await first.cached(user)).data.insumos[0].cantidad_actual, 11);
  assert.equal((await second.cached(otherUser)).data.insumos[0].cantidad_actual, 8);

  sessions[0].clear();
  navigator.onLine = true;
  await Promise.all([first.sync(user, 'token-7'), second.sync(otherUser, 'token-8')]);
  assert.equal(sent.length, 1);
  assert.equal(sent[0].token, 'Token token-8');
  assert.equal((await storage.listOperations(user.id_usuario)).length, 1);
  assert.equal((await storage.listOperations(otherUser.id_usuario)).length, 0);

  sessions[0].save('token-7', user);
  await first.sync(user, 'token-7');
  assert.equal(sent[1].token, 'Token token-7');
  assert.equal(operations.size, 0);
});

test('no confirma guardado ni envia cuando falla almacenamiento', async () => {
  const env = setup();
  env.storage.addOperation = async () => { throw new Error('Cuota agotada'); };
  await assert.rejects(env.client.save(user, 'token', 'entrada', payload()), /Cuota/);
  assert.equal(env.requests(), 0);
});

test('sincronizaciones simultaneas no envian dos veces', async () => {
  const env = setup();
  env.disconnect();
  await env.client.save(user, 'token', 'entrada', payload());
  env.reconnect();
  await Promise.all([env.client.sync(user, 'token'), env.client.sync(user, 'token')]);
  assert.equal(env.requests(), 1);
});

test('descartar rechazado revierte su efecto local', async () => {
  const env = setup();
  env.reject(true);
  const failed = await env.client.save(user, 'token', 'entrada', payload());
  assert.equal(failed.data.insumos[0].cantidad_actual, 10);
  const result = await env.client.discard(user, failed.operations[0].id);
  assert.equal(result.data.insumos[0].cantidad_actual, 10);
  assert.equal(result.operations.length, 0);
});

test('copias anteriores conservan pendientes sin duplicar su efecto', () => {
  const operation = createOperation(user, 'entrada', payload(), snapshot().insumos);
  const legacy = projectSnapshot(snapshot(), [operation]);
  const normalized = normalizeLegacySnapshot(legacy, [operation]);
  assert.equal(normalized.insumos[0].cantidad_actual, 10);
  assert.equal(projectSnapshot(normalized, [operation]).insumos[0].cantidad_actual, 12);
});
