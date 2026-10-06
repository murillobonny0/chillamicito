const fs = require('fs');
const path = require('path');

const input = process.argv[2] || 'artillery/reporte-stock.json';
const output = process.argv[3] || 'artillery/reporte-stock.html';
const titulo = process.argv[4] || 'Prueba de carga';
const data = JSON.parse(fs.readFileSync(input, 'utf8'));
const aggregate = data.aggregate || {};
const counters = aggregate.counters || {};
const summaries = aggregate.summaries || {};
const responseTime = summaries['http.response_time'] || {};

const value = (key) => counters[key] || 0;
const ms = (number) => `${Number(number || 0).toFixed(1)} ms`;
const percent = (ok, total) => total ? `${((ok / total) * 100).toFixed(1)}%` : '0.0%';

const totalRequests = value('http.requests');
const totalResponses = value('http.responses');
const okResponses = value('http.codes.200');
const forbiddenResponses = value('http.codes.403');
const failedUsers = value('vusers.failed');
const completedUsers = value('vusers.completed');
const timeoutErrors = value('errors.ERR_SOCKET_TIMEOUT');
const otherErrors = Object.entries(counters)
  .filter(([key]) => key.startsWith('errors.') && key !== 'errors.ERR_SOCKET_TIMEOUT');
const nonOkResponses = totalResponses - okResponses;

const endpointRows = Object.entries(counters)
  .filter(([key]) => key.startsWith('plugins.metrics-by-endpoint.') && key.includes('.codes.'))
  .map(([key, count]) => {
    const parts = key.replace('plugins.metrics-by-endpoint.', '').split('.codes.');
    return { endpoint: parts[0], code: parts[1], count };
  })
  .sort((a, b) => a.endpoint.localeCompare(b.endpoint) || a.code.localeCompare(b.code));

const riskItems = [];
if (timeoutErrors > 0) {
  riskItems.push(`Se detectaron ${timeoutErrors} timeouts; puede existir saturacion bajo carga alta o consultas pesadas.`);
}
if (failedUsers > 0) {
  riskItems.push(`${failedUsers} usuarios virtuales no completaron el flujo; revisar endpoints con mayor tiempo de respuesta.`);
}
if (forbiddenResponses > 0) {
  riskItems.push(`${forbiddenResponses} respuestas 403 muestran controles de permisos activos o accesos no autorizados.`);
}
if (nonOkResponses > 0 && forbiddenResponses === 0) {
  riskItems.push(`${nonOkResponses} respuestas no fueron 200; revisar codigos HTTP por endpoint.`);
}
if (Number(responseTime.p95 || 0) > 1000) {
  riskItems.push(`El percentil P95 supera 1000 ms (${ms(responseTime.p95)}); puede requerir optimizacion si la carga crece.`);
}
if (!riskItems.length) {
  riskItems.push('No se detectaron fallas durante la carga aplicada: las peticiones respondieron correctamente.');
}

const endpointTable = endpointRows.length
  ? endpointRows.map((row) => `<tr><td>${row.endpoint}</td><td>${row.code}</td><td>${row.count}</td></tr>`).join('')
  : '<tr><td colspan="3">Sin detalle por endpoint.</td></tr>';
const forbiddenRows = endpointRows.filter((row) => row.code === '403');
const forbiddenTable = forbiddenRows.length
  ? forbiddenRows.map((row) => `<tr><td>${row.endpoint}</td><td>${row.code}</td><td>${row.count}</td></tr>`).join('')
  : '<tr><td colspan="3">Sin bloqueos por permisos.</td></tr>';
const riskList = riskItems.map((item) => `<li>${item}</li>`).join('');
const errorRows = otherErrors.length
  ? otherErrors.map(([key, count]) => `<tr><td>${key}</td><td>${count}</td></tr>`).join('')
  : '<tr><td colspan="2">Sin errores adicionales.</td></tr>';

const html = `<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <title>${titulo} - Chillamicito</title>
  <style>
    body {
      background: #fff;
      color: #111;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
      line-height: 1.45;
      margin: 36px;
      max-width: 980px;
    }
    h1 {
      border-bottom: 2px solid #111;
      font-size: 22px;
      margin: 0 0 8px;
      padding-bottom: 8px;
    }
    h2 {
      border-bottom: 1px solid #111;
      font-size: 16px;
      margin: 28px 0 10px;
      padding-bottom: 4px;
    }
    .muted {
      color: #444;
      margin: 0 0 22px;
    }
    .summary {
      list-style: none;
      margin: 20px 0 26px;
      padding: 0;
    }
    .summary li {
      border-bottom: 1px solid #ddd;
      display: flex;
      justify-content: space-between;
      padding: 7px 0;
    }
    .summary strong {
      font-weight: 700;
    }
    table {
      border-collapse: collapse;
      margin: 10px 0 24px;
      width: 100%;
    }
    th, td {
      border-bottom: 1px solid #ddd;
      padding: 8px 0;
      text-align: left;
      vertical-align: top;
    }
    th {
      border-bottom: 1px solid #111;
      font-weight: 700;
    }
    ul {
      margin: 8px 0 24px 18px;
      padding: 0;
    }
    li {
      margin: 6px 0;
    }
  </style>
</head>
<body>
  <h1>${titulo}</h1>
  <p class="muted">Sistema Chillamicito - generado desde ${path.basename(input)}</p>

  <h2>Resumen</h2>
  <ul class="summary">
    <li><span>Peticiones HTTP</span><strong>${totalRequests}</strong></li>
    <li><span>Respuestas 200</span><strong>${okResponses}</strong></li>
    <li><span>Exito HTTP</span><strong>${percent(okResponses, totalResponses || totalRequests)}</strong></li>
    <li><span>Bloqueos por permisos</span><strong>${forbiddenResponses}</strong></li>
    <li><span>Usuarios completados</span><strong>${completedUsers}</strong></li>
    <li><span>Usuarios fallidos</span><strong>${failedUsers}</strong></li>
    <li><span>Timeouts</span><strong>${timeoutErrors}</strong></li>
  </ul>

  <h2>Tiempos de respuesta</h2>
  <table>
    <tr><th>Metrica</th><th>Valor</th></tr>
    <tr><td>Minimo</td><td>${ms(responseTime.min)}</td></tr>
    <tr><td>Promedio</td><td>${ms(responseTime.mean)}</td></tr>
    <tr><td>Mediana</td><td>${ms(responseTime.median)}</td></tr>
    <tr><td>P95</td><td>${ms(responseTime.p95)}</td></tr>
    <tr><td>P99</td><td>${ms(responseTime.p99)}</td></tr>
    <tr><td>Maximo</td><td>${ms(responseTime.max)}</td></tr>
  </table>

  <h2>Resultados por endpoint</h2>
  <table>
    <tr><th>Endpoint</th><th>Codigo HTTP</th><th>Cantidad</th></tr>
    ${endpointTable}
  </table>

  <h2>Bloqueos por permisos</h2>
  <table>
    <tr><th>Endpoint</th><th>Codigo HTTP</th><th>Cantidad</th></tr>
    ${forbiddenTable}
  </table>

  <h2>Posibles fallas observadas</h2>
  <ul>${riskList}</ul>

  <h2>Errores adicionales</h2>
  <table>
    <tr><th>Error</th><th>Cantidad</th></tr>
    ${errorRows}
  </table>
</body>
</html>`;

fs.writeFileSync(output, html, 'utf8');
console.log(`Reporte generado: ${output}`);
