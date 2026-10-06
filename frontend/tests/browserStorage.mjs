import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:http';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const browser = process.env.TEST_BROWSER || 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe';
const profile = await mkdtemp(join(tmpdir(), 'chillamicito-storage-test-'));
const script = `
import * as store from '/store.js';
const check = (condition, message) => { if (!condition) throw new Error(message); };
try {
  await Promise.all([store.mergeSnapshot('7', { insumos: [1] }), store.mergeSnapshot('7', { entradas: [2] })]);
  const snapshot = await store.getSnapshot('7');
  check(snapshot.insumos[0] === 1 && snapshot.entradas[0] === 2, 'Concurrent snapshot updates');
  await store.addOperation({ id: 'b', userId: '7', sequence: 1, createdAt: '2026-01-01' });
  await store.addOperation({ id: 'a', userId: '7', sequence: 2, createdAt: '2026-01-01' });
  await store.addOperation({ id: 'c', userId: '8', sequence: 1, createdAt: '2026-01-01' });
  const operations = await store.listOperations('7');
  check(operations.length === 2 && operations[0].id === 'b', 'User isolation and chronological order');
  await store.reconcileSnapshot('7', { insumos: [3] }, operations);
  check((await store.listOperations('7')).length === 0, 'Acknowledged operations');
  check((await store.getSnapshot('7')).insumos[0] === 3, 'Reconciled snapshot');
  check((await store.listOperations('8')).length === 1, 'Other user preserved');
  localStorage.setItem('chillamicito:snapshot:9', JSON.stringify({ insumos: [9] }));
  localStorage.setItem('chillamicito:operations:9', JSON.stringify([{ id: 'old', userId: '9', createdAt: '2026-01-01' }]));
  check((await store.listOperations('9'))[0].id === 'old', 'Legacy queue migration');
  check((await store.getSnapshot('9')).insumos[0] === 9, 'Legacy snapshot migration');
  check(!localStorage.getItem('chillamicito:operations:9'), 'Legacy migration committed');
  document.body.dataset.result = 'passed';
} catch (error) {
  document.body.dataset.result = 'failed';
  document.body.textContent = error.stack;
}
await fetch('/result', { method: 'POST', body: JSON.stringify({ passed: document.body.dataset.result === 'passed', error: document.body.textContent }) });
`;
const source = await readFile(new URL('../src/offlineStore.js', import.meta.url), 'utf8');
let receiveResult;
const completion = new Promise((resolve) => { receiveResult = resolve; });
const server = createServer((request, response) => {
  if (request.url === '/result') {
    let body = '';
    request.on('data', (chunk) => { body += chunk; });
    request.on('end', () => { response.end('OK'); receiveResult(JSON.parse(body)); });
    return;
  }
  response.setHeader('Content-Type', request.url === '/store.js' ? 'text/javascript' : 'text/html');
  response.end(request.url === '/store.js' ? source : `<body data-result="waiting"><script type="module">${script}</script></body>`);
});
await new Promise((resolve) => server.listen(0, '127.0.0.1', resolve));
let child;
let timer;
try {
  const result = await new Promise((resolve, reject) => {
    child = spawn(browser, ['--headless', '--disable-gpu', '--no-first-run', '--no-default-browser-check',
      `--user-data-dir=${profile}`, `http://127.0.0.1:${server.address().port}`], { windowsHide: true });
    let stderr = '';
    timer = setTimeout(() => reject(new Error(`Browser timeout: ${stderr.slice(-1000)}`)), 45000);
    child.stderr.on('data', (chunk) => { stderr += chunk; });
    child.on('error', (error) => { clearTimeout(timer); reject(error); });
    child.on('exit', (code) => reject(new Error(`Browser exit ${code}: ${stderr.slice(-1000)}`)));
    completion.then(resolve, reject);
  });
  assert.equal(result.passed, true, result.error);
  console.log('IndexedDB real: persistencia, concurrencia, orden, aislamiento y migracion correctos.');
} finally {
  clearTimeout(timer);
  if (child && child.exitCode === null) {
    const exited = new Promise((resolve) => child.once('exit', resolve));
    child.kill();
    await exited;
  }
  server.close();
  // Solo el perfil temporal exclusivo creado por esta prueba.
  await rm(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 300 });
}
