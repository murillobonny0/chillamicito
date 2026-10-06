export const isNetworkFailure = (error) => Boolean(error?.isAxiosError && !error.response && error.code !== 'ERR_CANCELED');

export function errorMessage(error) {
  const flatten = (value) => typeof value === 'string' ? value
    : Object.values(value || {}).map(flatten).filter(Boolean).join(' ');
  return flatten(error.response?.data) || error.message || 'No se pudo completar la operacion.';
}

export function projectSnapshot(snapshot = {}, operations = []) {
  const view = structuredClone(snapshot);
  view.insumos ||= [];
  for (const kind of ['entrada', 'salida', 'merma']) view[`${kind}s`] ||= [];
  for (const operation of operations.filter((item) => item.status !== 'error')) {
    const records = view[`${operation.kind}s`];
    // Compatibilidad con las primeras copias, que ya incluian movimientos locales.
    if (records.some((record) => record[`id_${operation.kind}`] === operation.id)) continue;
    records.unshift({ ...operation.record, pendiente: true });
    for (const delta of operation.stockDeltas) {
      const insumo = view.insumos.find((item) => Number(item.id_insumo) === Number(delta.id_insumo));
      if (insumo) insumo.cantidad_actual = Number((Number(insumo.cantidad_actual) + delta.cantidad).toFixed(3));
    }
  }
  return view;
}

export function normalizeLegacySnapshot(snapshot, operations) {
  if (!snapshot || snapshot.offlineVersion === 2) return snapshot;
  const base = structuredClone(snapshot);
  for (const operation of operations) {
    const name = `${operation.kind}s`;
    if (!base[name]?.some((item) => item[`id_${operation.kind}`] === operation.id)) continue;
    base[name] = base[name].filter((item) => item[`id_${operation.kind}`] !== operation.id);
    for (const delta of operation.stockDeltas) {
      const insumo = base.insumos?.find((item) => Number(item.id_insumo) === Number(delta.id_insumo));
      if (insumo) insumo.cantidad_actual = Number((Number(insumo.cantidad_actual) - delta.cantidad).toFixed(3));
    }
  }
  return { ...base, offlineVersion: 2 };
}

export function createOperation(user, kind, payload, insumos) {
  const id = crypto.randomUUID();
  const createdAt = new Date().toISOString();
  const details = kind === 'merma' ? [payload] : payload.detalles;
  if (!details?.length) throw new Error('Debe registrar al menos un insumo.');
  const totals = new Map();
  for (const detail of details) {
    const cantidad = Number(detail.cantidad);
    if (!Number.isFinite(cantidad) || cantidad <= 0) throw new Error('La cantidad debe ser mayor a cero.');
    totals.set(Number(detail.id_insumo), (totals.get(Number(detail.id_insumo)) || 0) + cantidad);
    if (kind === 'entrada' && (!Number.isFinite(Number(detail.costo_unitario)) || Number(detail.costo_unitario) < 0)) {
      throw new Error('El costo no puede ser negativo.');
    }
  }
  for (const [insumoId, cantidad] of totals) {
    const insumo = insumos.find((item) => Number(item.id_insumo) === insumoId);
    if (!insumo) throw new Error('El insumo no esta disponible en los datos locales.');
    const remaining = Math.round((Number(insumo.cantidad_actual) - cantidad) * 1000);
    const minimum = kind === 'salida' ? Math.round(Number(insumo.stock_minimo) * 1000) : 0;
    if (kind !== 'entrada' && remaining < minimum) throw new Error(`Stock insuficiente para ${insumo.nombre}.`);
  }
  if (kind === 'merma' && payload.motivo !== 'Recorte') throw new Error('El motivo de merma debe ser Recorte.');
  const decorated = details.map((detail, index) => {
    const insumo = insumos.find((item) => Number(item.id_insumo) === Number(detail.id_insumo));
    return {
      ...detail, [`id_detalle_${kind}`]: `${id}-${index}`, insumo: insumo.nombre,
      unidad: insumo.unidad, subtotal: Number(detail.cantidad) * Number(detail.costo_unitario || 0),
    };
  });
  return {
    id, userId: String(user.id_usuario), kind, createdAt, status: 'pending',
    endpoint: `/usuarios/stock/${kind}s/`, payload: { ...payload, id_operacion: id, fecha_operacion: createdAt },
    stockDeltas: [...totals].map(([id_insumo, cantidad]) => ({ id_insumo, cantidad: kind === 'entrada' ? cantidad : -cantidad })),
    record: {
      ...payload, [`id_${kind}`]: id, id_operacion: id, [`fecha_${kind}`]: createdAt,
      usuario: user.username, pendiente: true,
      ...(kind === 'merma' ? { insumo: decorated[0].insumo, unidad: decorated[0].unidad }
        : { detalles: decorated, total_compra: decorated.reduce((sum, item) => sum + item.subtotal, 0) }),
    },
  };
}

export function createStockClient(api, storage) {
  let chain = Promise.resolve();
  const locked = (user, action) => {
    const run = () => globalThis.navigator?.locks
      ? navigator.locks.request(`chillamicito-stock-${user.id_usuario}`, action) : action();
    const result = chain.then(run, run);
    chain = result.catch(() => undefined);
    return result;
  };
  const current = (token) => localStorage.getItem('token') === token;
  const requestConfig = (token) => ({ headers: { Authorization: `Token ${token}` } });
  const fetchSnapshot = async (user, token) => {
    const names = ['insumos', 'notificaciones'];
    if (user.rol === 'ayudante_cocina') names.push('entradas', 'salidas', 'mermas');
    else if (user.rol === 'propietario') names.push('mermas');
    const data = { offlineVersion: 2 };
    for (const name of names) {
      if (!current(token)) throw new Error('La sesion ha cambiado.');
      const response = await api.get(`/usuarios/stock/${name}/`, requestConfig(token));
      data[name] = response.data;
    }
    return data;
  };
  const cached = async (user) => {
    const operations = await storage.listOperations(user.id_usuario);
    const previous = await storage.getSnapshot(user.id_usuario);
    const snapshot = normalizeLegacySnapshot(previous, operations);
    if (snapshot !== previous) await storage.mergeSnapshot(user.id_usuario, snapshot);
    return { data: snapshot ? projectSnapshot(snapshot, operations) : null, operations };
  };
  const sync = async (user, token, retry = false) => {
    let operations = await storage.listOperations(user.id_usuario);
    let failure = null;
    if (navigator.onLine && current(token)) {
      for (const operation of operations) {
        if (!current(token)) break;
        if (operation.status === 'synced') continue;
        if (operation.status === 'error' && !retry) break;
        try {
          await api.post(operation.endpoint, operation.payload, requestConfig(token));
          await storage.addOperation({ ...operation, status: 'synced', error: null });
        } catch (error) {
          failure = error;
          if (error.response && error.response.status >= 400 && error.response.status < 500) {
            await storage.addOperation({ ...operation, status: 'error', canDiscard: [400, 403, 409].includes(error.response.status), error: errorMessage(error) });
          }
          break;
        }
      }
      operations = await storage.listOperations(user.id_usuario);
      if (!failure && operations.every((operation) => operation.status === 'synced') && current(token)) {
        try {
          const data = await fetchSnapshot(user, token);
          await storage.reconcileSnapshot(user.id_usuario, data, operations);
        } catch (error) { failure = error; }
      }
    }
    return { ...await cached(user), failure };
  };
  return {
    cached,
    sync: (user, token, retry) => locked(user, () => sync(user, token, retry)),
    save: (user, token, kind, payload) => locked(user, async () => {
      if (!current(token)) throw new Error('La sesion ha cambiado.');
      const { data, operations } = await cached(user);
      if (!data) throw new Error('Primero carga el stock con conexion.');
      if (operations.some((operation) => operation.status === 'error')) throw new Error('Revisa los movimientos pendientes antes de continuar.');
      const operation = createOperation(user, kind, payload, data.insumos);
      operation.sequence = Math.max(Date.now(), ...operations.map((item) => item.sequence || Date.parse(item.createdAt))) + 1;
      // Persiste antes del primer envio; una respuesta perdida se puede reintentar con el mismo ID.
      await storage.addOperation(operation);
      return sync(user, token);
    }),
    discard: (user, id) => locked(user, async () => {
      const operations = await storage.listOperations(user.id_usuario);
      const operation = operations.find((item) => item.id === id);
      if (operation?.status !== 'error' || !operation.canDiscard) throw new Error('Solo se pueden descartar movimientos rechazados.');
      await cached(user);
      await storage.removeOperation(id);
      return cached(user);
    }),
  };
}
