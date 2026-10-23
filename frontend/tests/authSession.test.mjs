import assert from 'node:assert/strict';
import { test } from 'node:test';
import { authSession, createAuthSession } from '../src/authSession.js';
import { createApiClient } from '../src/api.js';

const owner = { id_usuario: 1, username: 'propietario', rol: 'propietario' };
const assistant = { id_usuario: 2, username: 'ayudante', rol: 'ayudante_cocina' };

function tabStorage() {
  const values = new Map();
  return {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: (key) => values.delete(key),
  };
}

function tab() {
  const storage = tabStorage();
  const session = createAuthSession(storage);
  const api = createApiClient('http://localhost/api', session);
  api.defaults.adapter = async (config) => ({
    data: { authorization: config.headers.get('Authorization') ?? null },
    status: 200, statusText: 'OK', headers: {}, config,
  });
  return { storage, session, api };
}

test('dos pestanas conservan usuarios y credenciales distintos al consultar y cerrar sesion', async () => {
  const first = tab();
  const second = tab();
  first.session.save('owner-token', owner);
  second.session.save('assistant-token', assistant);

  const [firstResponse, secondResponse] = await Promise.all([
    first.api.get('/usuarios/perfil/'), second.api.get('/usuarios/perfil/'),
  ]);
  assert.equal(firstResponse.data.authorization, 'Token owner-token');
  assert.equal(secondResponse.data.authorization, 'Token assistant-token');
  assert.deepEqual(first.session.getUser(), owner);
  assert.deepEqual(second.session.getUser(), assistant);

  // Recargar reconstruye el lector sobre el almacenamiento de la misma pestana.
  const reloaded = createAuthSession(second.storage);
  assert.equal(reloaded.getToken(), 'assistant-token');
  assert.deepEqual(reloaded.getUser(), assistant);

  first.session.clear();
  assert.equal(first.session.getUser(), null);
  assert.equal((await first.api.get('/usuarios/perfil/')).data.authorization, null);
  assert.equal((await second.api.get('/usuarios/perfil/')).data.authorization, 'Token assistant-token');
  assert.deepEqual(second.session.getUser(), assistant);

  first.session.save('new-token', { ...owner, id_usuario: 3 });
  assert.equal(second.session.getToken(), 'assistant-token');
});

test('una pestana nueva ignora la credencial compartida de la version anterior', (t) => {
  const previous = ['sessionStorage', 'localStorage'].map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]);
  t.after(() => previous.forEach(([key, descriptor]) => {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }));
  const shared = tabStorage();
  shared.setItem('token', 'legacy-owner-token');
  shared.setItem('chillamicito:offline-user', JSON.stringify(owner));
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: shared });
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: tabStorage() });

  assert.equal(authSession.getToken(), null);
  assert.equal(authSession.getUser(), null);
  authSession.save('assistant-token', assistant);
  authSession.clear();
  assert.equal(shared.getItem('token'), 'legacy-owner-token');
});

test('una respuesta pendiente del usuario anterior se descarta sin afectar otra pestana', async () => {
  const first = tab();
  const second = tab();
  first.session.save('owner-token', owner);
  second.session.save('assistant-token', assistant);
  let finish;
  let started;
  const requestStarted = new Promise((resolve) => { started = resolve; });
  first.api.defaults.adapter = (config) => new Promise((resolve) => {
    finish = () => resolve({ data: { privado: true }, status: 200, statusText: 'OK', headers: {}, config });
    started();
  });
  const pending = first.api.get('/usuarios/gestion/');
  await requestStarted;
  first.session.clear();
  first.session.save('different-token', assistant);
  finish();

  await assert.rejects(pending, (error) => error.code === 'ERR_CANCELED');
  assert.equal((await second.api.get('/usuarios/perfil/')).data.authorization, 'Token assistant-token');
});

test('el cliente respeta la credencial explicita de los movimientos pendientes', async () => {
  const first = tab();
  first.session.save('owner-token', owner);
  const response = await first.api.get('/usuarios/stock/insumos/', {
    headers: { Authorization: 'Token operation-token' },
  });
  assert.equal(response.data.authorization, 'Token operation-token');
});
