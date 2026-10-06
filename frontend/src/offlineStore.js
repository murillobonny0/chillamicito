const DB_NAME = 'chillamicito-offline';

const openDatabase = () => new Promise((resolve, reject) => {
  const request = indexedDB.open(DB_NAME, 1);
  request.onupgradeneeded = () => {
    const db = request.result;
    if (!db.objectStoreNames.contains('snapshots')) db.createObjectStore('snapshots', { keyPath: 'userId' });
    if (!db.objectStoreNames.contains('operations')) {
      db.createObjectStore('operations', { keyPath: 'id' }).createIndex('userId', 'userId');
    }
  };
  request.onsuccess = () => resolve(request.result);
  request.onerror = () => reject(request.error);
  request.onblocked = () => reject(new Error('Cierra las otras pestanas para abrir el almacenamiento local.'));
});

async function transact(stores, mode, action) {
  const db = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(stores, mode);
      let result;
      // Una solicitud exitosa aun puede pertenecer a una transaccion abortada.
      tx.oncomplete = () => resolve(result);
      tx.onabort = () => reject(tx.error || new Error('No se pudo guardar en este dispositivo.'));
      tx.onerror = () => reject(tx.error);
      action(tx, (value) => { result = value; });
    });
  } finally {
    db.close();
  }
}

async function migrateLegacyStorage(userId) {
  const snapshotKey = `chillamicito:snapshot:${userId}`;
  const operationsKey = `chillamicito:operations:${userId}`;
  const snapshot = localStorage.getItem(snapshotKey);
  const operations = localStorage.getItem(operationsKey);
  if (!snapshot && !operations) return;
  const parsedSnapshot = snapshot ? JSON.parse(snapshot) : null;
  const parsedOperations = operations ? JSON.parse(operations) : [];
  await transact(['snapshots', 'operations'], 'readwrite', (tx) => {
    const snapshots = tx.objectStore('snapshots');
    snapshots.get(String(userId)).onsuccess = (event) => {
      if (!event.target.result && parsedSnapshot) snapshots.put({ userId: String(userId), data: parsedSnapshot });
    };
    const pending = tx.objectStore('operations');
    for (const operation of parsedOperations) {
      pending.get(operation.id).onsuccess = (event) => {
        if (!event.target.result) pending.put(operation);
      };
    }
  });
  localStorage.removeItem(snapshotKey);
  localStorage.removeItem(operationsKey);
}

export async function getSnapshot(userId) {
  await migrateLegacyStorage(userId);
  return transact(['snapshots'], 'readonly', (tx, done) => {
    tx.objectStore('snapshots').get(String(userId)).onsuccess = (event) => done(event.target.result?.data || null);
  });
}

export function mergeSnapshot(userId, changes) {
  return transact(['snapshots'], 'readwrite', (tx, done) => {
    const store = tx.objectStore('snapshots');
    store.get(String(userId)).onsuccess = (event) => {
      const data = { ...event.target.result?.data, ...changes, updatedAt: new Date().toISOString() };
      store.put({ userId: String(userId), data });
      done(data);
    };
  });
}

export function addOperation(operation) {
  return transact(['operations'], 'readwrite', (tx) => { tx.objectStore('operations').put(operation); });
}

export async function listOperations(userId) {
  await migrateLegacyStorage(userId);
  return transact(['operations'], 'readonly', (tx, done) => {
    tx.objectStore('operations').index('userId').getAll(String(userId)).onsuccess = (event) => {
      done(event.target.result.sort((a, b) => (a.sequence || Date.parse(a.createdAt)) - (b.sequence || Date.parse(b.createdAt)) || a.id.localeCompare(b.id)));
    };
  });
}

export function removeOperation(id) {
  return transact(['operations'], 'readwrite', (tx) => { tx.objectStore('operations').delete(id); });
}

export function reconcileSnapshot(userId, data, operations) {
  // Reemplaza la base y los confirmados juntos para no descontarlos dos veces tras recargar.
  return transact(['snapshots', 'operations'], 'readwrite', (tx) => {
    tx.objectStore('snapshots').put({ userId: String(userId), data: { ...data, updatedAt: new Date().toISOString() } });
    for (const operation of operations) tx.objectStore('operations').delete(operation.id);
  });
}
