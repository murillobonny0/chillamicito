# Mapa funcional del sistema Chillamicito

Este documento resume como funciona el sistema, que archivos intervienen y como explicar cada parte en defensa. El proyecto esta dividido en frontend React, backend Django, base de datos PostgreSQL/Supabase, ETL/Data Mart y despliegue en la nube.

## 1. Arquitectura general

Flujo principal:

1. El usuario entra al frontend publicado en Vercel.
2. React envia usuario y contrasena al backend Django publicado en Railway.
3. Django valida las credenciales y devuelve un token.
4. React guarda el token en `localStorage`.
5. Cada peticion posterior viaja con `Authorization: Token <token>`.
6. Django aplica permisos segun el rol del usuario.
7. Las operaciones de stock se guardan en PostgreSQL/Supabase.
8. El ETL transforma entradas, salidas y mermas hacia el Data Mart.
9. Reportes y dashboards leen datos resumidos desde el backend BI.

Arquitectura en nube:

- Frontend: Vercel, URL `https://challamix.vercel.app/`.
- Backend: Railway, URL `https://challamix-production.up.railway.app`.
- Base de datos: Supabase PostgreSQL.
- Conexion del frontend al backend: `VITE_API_URL=https://challamix-production.up.railway.app/api`.
- Conexion del backend a Supabase: variables `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

Respuesta de defensa:

El sistema esta separado por responsabilidades. Vercel sirve la interfaz, Railway ejecuta Django y Supabase almacena la informacion. Esto permite ingresar desde laptop o celular sin depender del servidor local.

## 2. Autenticacion, roles y permisos

Archivos principales:

- `backend/usuarios/models.py`
- `backend/usuarios/serializers.py`
- `backend/usuarios/views.py`
- `frontend/src/api.js`
- `frontend/src/App.jsx`

Modelos:

- `Rol`: define perfiles como propietario, chef y ayudante de cocina.
- `Permiso`: define acciones disponibles.
- `RolPermiso`: relaciona roles con permisos.
- `Usuario`: usuario personalizado de Django.

Funcionamiento en codigo:

- `LoginView` valida usuario y contrasena.
- Django crea o recupera un token de DRF.
- `frontend/src/api.js` agrega el token automaticamente a cada peticion.
- `App.jsx` muestra modulos distintos segun `usuario.rol`.

Permisos actuales:

- Propietario: gestiona usuarios, roles/permisos, consulta stock, alertas, reportes y dashboards BI.
- Ayudante de cocina: registra insumos, entradas, salidas y mermas; tambien consulta stock.
- Chef: consulta stock, disponibilidad y alertas.

Respuesta de defensa:

El propietario toma decisiones y revisa informacion. La parte operativa de ingreso y salida de stock queda en manos del ayudante de cocina, que en este caso es Maria. Esto separa la administracion de la operacion diaria.

## 3. Stock e insumos

Archivos principales:

- `backend/usuarios/models.py`
- `backend/usuarios/serializers.py`
- `backend/usuarios/views.py`
- `backend/usuarios/alertas.py`
- `frontend/src/App.jsx`

Modelos:

- `Categoria`
- `UnidadMedida`
- `Insumo`
- `Stock`

Campos importantes:

- `Insumo.stock_minimo`: limite minimo para controlar compras.
- `Stock.cantidad_actual`: cantidad disponible real.

Regla:

```text
stock_actual <= stock_minimo        => stock critico
stock_actual <= stock_minimo * 1.25 => stock preventivo
```

Respuesta de defensa:

El stock minimo no es el stock disponible, es el punto de control. Si la cantidad actual se acerca al minimo, el sistema genera una alerta preventiva. Si llega al minimo o baja, se considera critico.

## 4. Locoto y conversion por arroba

Archivos modificados:

- `frontend/src/App.jsx`
- `backend/usuarios/views.py`
- `backend/usuarios/migrations/0016_agregar_locoto.py`
- `backend/usuarios/etl.py`

Configuracion:

- Locoto pertenece a categoria Verduras.
- Unidad base: kilo.
- Compra permitida en frontend: arroba.
- Conversion: `1 arroba = 11 kg`.
- Stock minimo: `2 kg`.
- Receta por plato entero: `0.100 kg`.
- Receta por medio plato: `0.050 kg`.

Funcionamiento:

En el frontend, si el insumo seleccionado es Locoto, el tipo de compra se limita a `Arroba - 11 kg`. React convierte la compra a kilos antes de enviarla al backend.

Calculo:

```text
cantidad_kg = cantidad_compra * 11
```

Respuesta de defensa:

Aunque el restaurante compra locoto por arroba, el stock se controla en kilos para mantener una unidad comun con los reportes, las salidas y el Data Mart.

## 5. Entradas de insumos

Archivos principales:

- `frontend/src/App.jsx`
- `backend/usuarios/serializers.py`
- `backend/usuarios/models.py`

Modelos:

- `Entrada`
- `DetalleEntrada`
- `Stock`

Funcionamiento:

1. Maria registra una entrada.
2. El frontend convierte la compra a kilos si corresponde.
3. El backend crea `Entrada` y sus `DetalleEntrada`.
4. Por cada detalle, el backend suma al stock.

Calculos:

```text
cantidadKg = cantidadCompra * factor
costoUnitarioKg = costoCompra / factor
totalCompra = cantidadCompra * costoCompra
stock_actual = stock_actual + cantidadKg
```

Dias usados en la carga realista:

- Carnes: martes, jueves y sabado.
- Verduras y papa: jueves o viernes.
- Las entradas se cargaron aproximadamente a las 9:00.

Respuesta de defensa:

Las entradas representan abastecimiento. El sistema registra cuanto ingreso, a que costo y actualiza inmediatamente el stock disponible.

## 6. Salidas por venta de platos

Archivos principales:

- `frontend/src/App.jsx`
- `backend/usuarios/serializers.py`
- `backend/usuarios/alertas.py`

Modelos:

- `Salida`
- `DetalleSalida`
- `Stock`
- `Notificacion`

Receta:

React arma los detalles de salida segun plato, tamano y cantidad de platos.

```text
cantidad_salida = cantidad_base_receta * factor_tamano * cantidad_platos
```

Factores:

- Entero: `1`
- Medio: `0.5`

Precios estimados:

- Macho, Borracho y Chillami: medio `Bs 130`, entero `Bs 185`.
- Brasa y Surubi: medio `Bs 150`, entero `Bs 225`.

Validacion:

Antes de guardar, el backend valida que la salida no deje un insumo por debajo del minimo.

```text
stock_resultante = stock_actual - cantidad_salida
```

Respuesta de defensa:

La salida no se registra por insumo manualmente, sino por plato vendido. El sistema calcula automaticamente los ingredientes usados y descuenta el stock.

## 7. Mermas

Archivos principales:

- `frontend/src/App.jsx`
- `backend/usuarios/serializers.py`
- `backend/usuarios/models.py`
- `backend/usuarios/etl.py`

Modelo:

- `Merma`

Funcionamiento:

La merma registra perdidas reales de insumo. No representa una venta ni aumenta platos vendidos. En el sistema el motivo queda como `Recorte` y la observacion explica la causa: grasa, golpe, dano o parte no utilizable.

Ejemplos:

- Papa golpeada durante seleccion.
- Recorte de carne por grasa.
- Tomate o cebolla con partes danadas.
- Locoto danado al seleccionar porciones.

Respuesta de defensa:

La merma permite medir perdidas. Se descuenta del stock y luego el BI calcula la perdida economica estimada para restarla de la ganancia final.

## 8. Alertas y notificaciones

Archivo principal:

- `backend/usuarios/alertas.py`

Modelo:

- `Notificacion`

Tipos:

- `stock_preventivo`
- `stock_minimo`
- `agotado`
- `stock_insuficiente`
- `feriado`

Reglas:

```text
stock_actual <= stock_minimo              => alerta critica
stock_actual <= stock_minimo * 1.25       => alerta preventiva
salida no permitida si rompe el minimo    => stock insuficiente
```

Respuesta de defensa:

Las alertas se generan automaticamente. Sirven para avisar antes de quedarse sin insumos y para evitar registrar salidas que no se pueden abastecer.

## 9. ETL y Data Mart

Archivo principal:

- `backend/usuarios/etl.py`

Tablas dimensionales:

- `DimCategoria`
- `DimInsumo`
- `DimTiempo`
- `DimUsuario`
- `DimTipoMovimiento`

Tabla de hechos:

- `HechoMovimientoStock`

Control de ejecucion:

- `RegistroETL`

Funcionamiento:

El ETL limpia y reconstruye el Data Mart. Lee entradas, salidas y mermas en orden cronologico. Por cada movimiento genera un hecho con cantidad, costo, stock resultante, estado de stock, tipo de movimiento y dimensiones relacionadas.

Calculos:

```text
costo_total_entrada = cantidad * costo_unitario
costo_promedio = total_comprado / cantidad_comprada
costo_total_salida = cantidad_consumida * costo_promedio
costo_total_merma = cantidad_merma * costo_promedio
```

Tambien se precargan insumos activos en `DimInsumo`, incluso si todavia no tienen movimientos, para que el BI pueda mostrar insumos como Locoto desde el inicio.

Resultado de la ultima carga:

- Movimientos en Data Mart: `10013`.
- Entradas transformadas: `242` detalles.
- Salidas transformadas: `9729` detalles.
- Mermas transformadas: `42`.
- Filas omitidas: `0`.
- Alertas de stock negativo: `0`.

Respuesta de defensa:

El ETL convierte datos operativos en informacion analitica. Asi los reportes y dashboards no dependen de consultas sueltas, sino de una estructura preparada para analisis historico.

## 10. Reportes

Archivos principales:

- `backend/usuarios/views.py`
- `frontend/src/App.jsx`

Endpoint:

```text
/api/usuarios/bi/dashboard/
```

Los reportes muestran:

- Ventas.
- Ganancia.
- Total vendido en kg.
- Compras.
- Costo de insumos usados.
- Merma.
- Resumen mensual.
- Historial diario de ventas.
- Consumo por insumo.
- Compras por insumo.

PDF mensual:

Cada mes puede descargarse en PDF con:

- Ventas.
- Platos vendidos.
- Consumo de insumos.
- Costo de insumos usados.
- Compras.
- Merma registrada.
- Perdida por merma.
- Ganancia antes de merma.
- Ganancia final descontando merma.

Busqueda de historial:

El reporte permite buscar ventas por:

- Fecha.
- Mes.
- Cantidad de platos.
- Monto.

Respuesta de defensa:

Los reportes sirven para revisar el detalle historico y descargar evidencias en PDF. La ganancia final descuenta el costo de insumos usados y la perdida por merma.

## 11. Dashboards BI

Archivos principales:

- `backend/usuarios/views.py`
- `frontend/src/App.jsx`

KPIs principales:

1. Stock actual frente al minimo.
2. Platos disponibles por tipo.
3. Demanda promedio por dia y franja horaria.
4. Variacion y tendencia de ventas/consumo.
5. Cobertura y riesgo de desabastecimiento.
6. Merma por insumo.
7. Cumplimiento de meta de ventas.

Indicador 1:

Cuenta insumos criticos y preventivos. Antes solo contaba los que estaban exactamente en minimo o por debajo; ahora tambien cuenta los cercanos al minimo.

Indicador 2:

Calcula cuantos platos enteros se pueden preparar con el stock actual y muestra el insumo limitante. Por ejemplo, si Locoto o Surubi es el insumo mas bajo, limita la cantidad posible.

Indicador 4:

Muestra tendencia semanal. Las fechas del eje son el inicio de semana, normalmente lunes. No significa que se vendio solo lunes; significa que la semana inicia en esa fecha. Una semana puede cruzar de junio a julio.

Respuesta de defensa:

El dashboard no solo muestra datos, tambien orienta decisiones: que comprar primero, cuanta produccion se puede atender y donde se generan perdidas.

## 12. Datos operativos realistas

Periodo cargado:

- Desde `02/06/2026`.
- Hasta `14/09/2026`.

Reglas usadas:

- Atencion regular: martes a domingo.
- Feriado lunes `14/09/2026`: se atiende por aniversario de Cochabamba.
- Martes a jueves: entre 10 y 20 platos diarios.
- Viernes: entre 20 y 30 platos diarios.
- Sabado: entre 40 y 60 platos diarios.
- Domingo y feriados: entre 60 y 100 platos diarios.
- Horarios de pedidos variados desde mediodia.

Resumen actual:

- Entradas: `61`.
- Salidas/pedidos: `1672`.
- Mermas: `42`.
- Platos vendidos: `3106`.
- Ventas estimadas: `Bs 538.710,00`.

Ventas por mes:

- Junio: `808 platos`, `Bs 141.885,00`.
- Julio: `841 platos`, `Bs 145.385,00`.
- Agosto: `991 platos`, `Bs 169.760,00`.
- Septiembre al 14: `466 platos`, `Bs 81.680,00`.

Stock final:

- Carne: `55 kg`, minimo `50 kg`.
- Papa: `165 kg`, minimo `150 kg`.
- Chorizo normal: `14.3 kg`, minimo `13 kg`.
- Chorizo parrillero: `14.3 kg`, minimo `13 kg`.
- Tomate: `6.6 kg`, minimo `6 kg`.
- Cebolla: `6.6 kg`, minimo `6 kg`.
- Locoto: `2.2 kg`, minimo `2 kg`.
- Surubi: `6.6 kg`, minimo `6 kg`.

Respuesta de defensa:

Los datos fueron cargados como historial operativo aproximado porque el restaurante no tenia registro digital previo de ventas. Se respetaron dias reales de atencion, abastecimiento y rangos de demanda informados por el negocio.

## 13. Feriados y sincronizacion

Archivos principales:

- `backend/usuarios/views.py`
- `frontend/src/App.jsx`

Funcionamiento:

El modulo de feriados sincroniza fechas importantes y crea notificaciones preventivas para planificar produccion y compras. En pantalla se muestra como `Sincronizar`, sin exponer detalles tecnicos al usuario final.

Respuesta de defensa:

Los feriados se usan para planificar demanda. Si una fecha especial genera mayor venta, el sistema ayuda a anticipar compras y produccion.

## 14. Pruebas con Artillery

Carpeta:

- `artillery/`

Archivos:

- `artillery/stock.yml`
- `artillery/usuarios.yml`
- `artillery/generar-reporte.js`
- `artillery/reporte-stock.html`
- `artillery/reporte-usuarios.html`

Objetivo:

Artillery se usa para probar carga y comportamiento de endpoints. No forma parte del codigo principal del sistema, sino de pruebas externas.

Escenarios:

- Stock: consulta catalogos, insumos y movimientos.
- Usuarios: prueba login y rutas de gestion.

Respuesta de defensa:

Artillery simula usuarios haciendo peticiones al backend. Sirve para observar tiempos de respuesta, errores HTTP y comportamiento bajo carga. No modifica la logica del sistema.

## 15. Despliegue en la nube

Archivos/configuracion:

- `backend/config/settings.py`
- `backend/requirements.txt`
- `frontend/src/api.js`

Railway:

- Ejecuta el backend Django.
- Usa Daphne porque el proyecto trabaja con ASGI y Channels.
- Comando de inicio:

```bash
daphne -b 0.0.0.0 -p $PORT config.asgi:application
```

- Comando de build:

```bash
pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput
```

Supabase:

- Guarda la base PostgreSQL.
- Railway se conecta mediante el pooler para evitar problemas de IPv6.

Vercel:

- Publica el frontend.
- Usa la variable:

```text
VITE_API_URL=https://challamix-production.up.railway.app/api
```

WhiteNoise:

Se agrego `whitenoise` para servir archivos estaticos de Django en produccion, especialmente el admin. No cambia la logica de negocio.

Respuesta de defensa:

El despliegue separa frontend, backend y base de datos. WhiteNoise solo resuelve archivos estaticos en Railway; no altera stock, ventas, reportes ni BI.

## 16. Verificacion final

Estado verificado:

- Frontend Vercel responde `200`.
- Backend Railway responde y muestra admin.
- Supabase contiene tablas y datos.
- Login de propietario Bonny funciona.
- Django `check` no reporta errores.
- ETL ejecutado sin filas omitidas.
- Reportes y dashboards se conectan al Data Mart.

Recomendacion para defensa:

No registrar datos nuevos en la nube antes de exponer, salvo que sea parte de una demostracion controlada. Si se registra una entrada, el stock sube inmediatamente. Si se registra una salida, el backend valida que exista stock suficiente y que no baje del minimo permitido.
