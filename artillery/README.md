# Pruebas de carga con Artillery

Artillery no se integra dentro de `views.py` ni dentro de React. Es una herramienta externa que simula usuarios consumiendo la API del sistema para medir rendimiento, respuestas correctas y posibles puntos de falla.

## Archivos

- `stock.yml`: prueba del modulo de stock, entradas, salidas, alertas y dashboard BI.
- `usuarios.yml`: prueba del modulo de usuarios, roles, permisos y control de acceso.
- `generar-reporte.js`: convierte el JSON oficial de Artillery en un reporte HTML local.

## Usuarios usados

- `Maria` / `maria33`: ayudante de cocina.
- `Bonny` / `bonny22`: propietario.

## Ejecutar pruebas

Primero levantar el backend:

```powershell
cd backend
python manage.py runserver 127.0.0.1:8000
```

En otra terminal, desde la raiz del proyecto:

```powershell
npx artillery@latest run artillery/stock.yml -o artillery/reporte-stock.json
node artillery/generar-reporte.js artillery/reporte-stock.json artillery/reporte-stock.html "Reporte de carga - Stock"
```

```powershell
npx artillery@latest run artillery/usuarios.yml -o artillery/reporte-usuarios.json
node artillery/generar-reporte.js artillery/reporte-usuarios.json artillery/reporte-usuarios.html "Reporte de carga - Usuarios"
```

## Como leer resultados

- `http.requests`: total de peticiones enviadas a Django.
- `http.responses`: total de respuestas recibidas.
- `http.codes.200`: respuestas correctas.
- `http.codes.403`: accesos bloqueados por permisos.
- `vusers.created`: usuarios virtuales simulados.
- `vusers.completed`: usuarios virtuales que terminaron el flujo.
- `vusers.failed`: usuarios virtuales que no completaron el flujo.
- `http.response_time.mean`: tiempo promedio de respuesta.
- `http.response_time.p95`: el 95% de respuestas fue igual o menor a ese tiempo.
- `http.response_time.p99`: el 99% de respuestas fue igual o menor a ese tiempo.
- `errors.ERR_SOCKET_TIMEOUT`: peticiones que tardaron demasiado y fueron cortadas.

## Posibles fallas que detecta

- Lentitud en endpoints de stock o BI.
- Errores 500 por fallas internas del backend.
- Errores 401 por problemas de autenticacion.
- Errores 403 por permisos insuficientes.
- Timeouts cuando la carga supera la capacidad del servidor local.
- Usuarios virtuales fallidos cuando no logran completar el flujo.

Para la defensa se puede explicar que Artillery simula concurrencia real contra la API y permite validar si el sistema responde correctamente bajo una carga controlada.
