import { useEffect, useMemo, useRef, useState } from 'react';
import ReactECharts from 'echarts-for-react';
import { createMonthlyReportPdf, monthlyReportFilename } from './monthlyReportPdf';
import api from './api';
import * as offlineStore from './offlineStore';
import { createStockClient, errorMessage, isNetworkFailure } from './stockOffline';

const stockClient = createStockClient(api, offlineStore);

// Estado inicial del formulario de inicio de sesion.
const initialForm = {
  username: '',
  password: '',
};

// Estado inicial para crear o editar usuarios desde el panel del propietario.
const initialUserForm = {
  id_usuario: null,
  nombre: '',
  apellido: '',
  username: '',
  correo: '',
  id_rol: '',
  estado: true,
  password: '',
};

// Estado inicial para registrar entradas de insumos.
const initialEntradaForm = {
  id_insumo: '',
  tipo_compra: 'kilo',
  cantidad_compra: 1,
  costo_compra: 0,
  observacion: '',
};

// Estado inicial para modificar el nivel minimo usado por alertas, salidas y BI.
const initialStockMinimoForm = {
  id_insumo: null,
  nombre: '',
  unidad: '',
  stock_minimo: '',
};

// Estado inicial para registrar salidas de insumos por plato vendido.
const initialSalidaForm = {
  plato: 'Macho',
  tamano: 'entero',
  cantidad_platos: 1,
  observacion: '',
};

const initialMermaForm = {
  id_insumo: '',
  cantidad: 1,
  motivo: 'Recorte',
  observacion: '',
};

// Estructura inicial del dashboard BI antes de cargar datos desde Django.
const initialBiData = {
  ultimo_etl: null,
  resumen: {},
  consumo_por_insumo: [],
  entradas_por_insumo: [],
  movimiento_por_categoria: [],
  tendencia: [],
  stock_actual: [],
  consumo_mensual: [],
  compras_mensual: [],
  merma_mensual: [],
  gastos_por_insumo: [],
  rotacion_por_insumo: [],
  alertas_compra: [],
  meses_clave: [],
  demanda_por_dia_franja: [],
  platos_disponibles: [],
  cobertura_estimada_stock: [],
  tendencia_consumo_semanal: [],
  tendencia_ventas_consumo: [],
  merma_por_insumo: [],
  ganancias_diarias: [],
  ganancias_semanales: [],
  ganancias_mensuales: [],
  kpis_decision: [],
  analisis_complementarios: {},
};

const readOfflineUser = () => {
  try {
    const value = localStorage.getItem('chillamicito:offline-user');
    return value ? JSON.parse(value) : null;
  } catch {
    return null;
  }
};

// Insumos base que se usan para calcular disponibilidad de produccion.
const insumosProduccion = ['Carne', 'Papa', 'Chorizo normal', 'Chorizo parrillero', 'Tomate', 'Cebolla', 'Locoto', 'Surubi'];

// Referencia visual de cantidades para un plato entero.
const recetaPlatoEntero = [
  { nombre: 'Papa', cantidad: '1 kg' },
  { nombre: 'Carne', cantidad: '1 kg' },
  { nombre: 'Chorizo', cantidad: '0.300 kg solo en piques de carne' },
  { nombre: 'Tomate', cantidad: '0.150 kg' },
  { nombre: 'Cebolla', cantidad: '0.150 kg' },
  { nombre: 'Locoto', cantidad: '0.100 kg' },
];

// Referencia visual de cantidades para medio plato.
const recetaMedioPlato = [
  { nombre: 'Papa', cantidad: '0.500 kg' },
  { nombre: 'Carne', cantidad: '0.500 kg' },
  { nombre: 'Chorizo', cantidad: '0.150 kg solo en piques de carne' },
  { nombre: 'Tomate', cantidad: '0.075 kg' },
  { nombre: 'Cebolla', cantidad: '0.075 kg' },
  { nombre: 'Locoto', cantidad: '0.050 kg' },
];

// Relacion entre platos y tipo de carne usada en cocina.
const carnesPorPlato = [
  'Chillami: lapping',
  'Macho y Borracho: tortuguita',
  'Brasa: lomo',
  'Surubi: surubi',
];

// Recetas usadas para descontar automaticamente insumos al registrar salidas.
const recetasPorPlato = {
  Chillami: [
    ['Papa', 1],
    ['Carne', 1],
    ['Chorizo normal', 0.3],
    ['Tomate', 0.15],
    ['Cebolla', 0.15],
    ['Locoto', 0.1],
  ],
  Macho: [
    ['Papa', 1],
    ['Carne', 1],
    ['Chorizo normal', 0.3],
    ['Tomate', 0.15],
    ['Cebolla', 0.15],
    ['Locoto', 0.1],
  ],
  Borracho: [
    ['Papa', 1],
    ['Carne', 1],
    ['Chorizo normal', 0.3],
    ['Tomate', 0.15],
    ['Cebolla', 0.15],
    ['Locoto', 0.1],
  ],
  Brasa: [
    ['Papa', 1],
    ['Carne', 1],
    ['Chorizo parrillero', 0.3],
    ['Tomate', 0.15],
    ['Cebolla', 0.15],
    ['Locoto', 0.1],
  ],
  Surubi: [
    ['Papa', 1],
    ['Surubi', 1],
    ['Tomate', 0.15],
    ['Cebolla', 0.15],
    ['Locoto', 0.1],
  ],
};

// Factor que convierte un plato entero o medio plato a cantidades de receta.
const factorTamano = {
  entero: 1,
  medio: 0.5,
};

// Precios entregados por el negocio para estimar ventas por plato.
const preciosPorPlato = {
  Macho: { medio: 130, entero: 185 },
  Borracho: { medio: 130, entero: 185 },
  Chillami: { medio: 130, entero: 185 },
  Brasa: { medio: 150, entero: 225 },
  Surubi: { medio: 150, entero: 225 },
};

const formatCantidad = (value) => {
  // Formatea cantidades evitando decimales innecesarios en la interfaz.
  const numberValue = Number(value || 0);
  const rounded = Math.round(numberValue * 1000) / 1000;
  const nearestInteger = Math.round(rounded);

  if (Math.abs(rounded - nearestInteger) <= 0.001) {
    return String(nearestInteger);
  }

  return rounded.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
};

const formatMoney = (value) => `Bs ${Number(value || 0).toLocaleString('es-BO', {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
})}`;

const formatDateTime = (value) => (value ? new Date(value).toLocaleString() : 'Pendiente');

const mesesNombre = [
  'Enero',
  'Febrero',
  'Marzo',
  'Abril',
  'Mayo',
  'Junio',
  'Julio',
  'Agosto',
  'Septiembre',
  'Octubre',
  'Noviembre',
  'Diciembre',
];

const getDateParts = (value) => {
  const dateText = String(value || '').slice(0, 10);
  const [year, month, day] = dateText.split('-').map(Number);

  if (!year || !month) {
    return null;
  }

  return { year, month, day: day || 1 };
};

const formatDateOnly = (value) => {
  const parts = getDateParts(value);
  if (!parts) {
    return 'Sin fecha';
  }

  return `${String(parts.day).padStart(2, '0')}/${String(parts.month).padStart(2, '0')}/${parts.year}`;
};

const monthNameFromDate = (value) => {
  const parts = getDateParts(value);
  return parts ? mesesNombre[parts.month - 1] : 'Sin mes';
};

const tendenciaTexto = (value, estado) => {
  // Convierte la variacion numerica en una lectura clara para el indicador de tendencia.
  if (value === null || value === undefined) {
    return 'Semana base';
  }

  const variacion = Number(value || 0);
  const movimiento = variacion > 0 ? 'Subio' : variacion < 0 ? 'Bajo' : 'Sin cambio';

  return `${movimiento} ${Math.abs(variacion).toFixed(1)}% - ${estado || 'estable'}`;
};

const formatKpiValue = (kpi) => {
  if (!kpi) {
    return 'Sin datos';
  }

  if (kpi.codigo === 'meta_ventas' || kpi.unidad === '%') {
    return `${Number(kpi.valor || 0).toFixed(1)}%`;
  }

  if (kpi.unidad === 'dias') {
    return `${Number(kpi.valor || 0).toFixed(1)} dias`;
  }

  if (kpi.codigo === 'tendencia_ventas_consumo') {
    return kpi.valor === null || kpi.valor === undefined ? 'Sin referencia' : `${Number(kpi.valor || 0).toFixed(1)}%`;
  }

  return `${formatCantidad(kpi.valor)} ${kpi.unidad || ''}`.trim();
};

const businessChartPalette = ['#1f6f8b', '#c3423f', '#2f8f6f', '#d59b2d', '#6f5fb8', '#4b5563', '#8a4f2f'];

const chartTextStyle = {
  color: '#30413b',
  fontFamily: 'Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
};

const tooltipStyle = {
  backgroundColor: 'rgba(255, 255, 255, 0.96)',
  borderColor: '#dce8e2',
  borderWidth: 1,
  padding: 12,
  textStyle: chartTextStyle,
};

const gridStyle = {
  left: 48,
  right: 24,
  top: 42,
  bottom: 44,
};

function BiChart({ option, height = 320, onEvents }) {
  return (
    <ReactECharts
      className="echart"
      notMerge
      onEvents={onEvents}
      option={option}
      style={{ height }}
    />
  );
}

// Etiquetas de estados de notificacion para mostrar texto en espanol.
const labelsEstadoNotificacion = {
  pendiente: 'Pendiente',
  leida: 'Leída',
};

// Etiquetas de tipos de notificacion para evitar mostrar codigos internos.
const labelsTipoNotificacion = {
  stock_minimo: 'Stock mínimo',
  stock_preventivo: 'Stock preventivo',
  agotado: 'Producto agotado',
  stock_insuficiente: 'Stock insuficiente',
  feriado: 'Feriado / planificación',
};

// Traducciones de respaldo para alertas antiguas o datos que lleguen en ingles.
const traduccionesAlertas = {
  'Feast of the Virgin of Candelaria': 'Fiesta de la Virgen de Candelaria',
  'Agrarian Reform Day': 'Día de la Reforma Agraria',
  'Stock minimo': 'Stock mínimo',
  Minimo: 'Mínimo',
  Planificacion: 'Planificación',
};

const textoAlerta = (value = '') =>
  // Reemplaza textos conocidos por su version en espanol antes de renderizar.
  Object.entries(traduccionesAlertas).reduce(
    (texto, [original, traducido]) => texto.replaceAll(original, traducido),
    value,
  );

const isStockMinimo = (insumo) => Number(insumo?.cantidad_actual || 0) <= Number(insumo?.stock_minimo || 0);

// Factores para convertir compras comerciales a kilos manejados por stock.
const factoresCompraKg = {
  kilo: 1,
  carga: 100,
  caja: 100,
  arroba: 11,
};

// Texto usado para mostrar el tipo de compra seleccionado.
const labelsCompra = {
  kilo: 'kilo',
  carga: 'carga',
  caja: 'caja',
  arroba: 'arroba',
};

// Define los modulos visibles para cada rol dentro del dashboard.
const dashboards = {
  propietario: {
    title: 'Propietario',
    subtitle: '',
    actions: [
      'Gestionar usuarios',
      'Gestionar roles y permisos',
      'Consultar stock',
      'Ver reportes',
      'Ver dashboards',
      'Consultar feriados',
      'Atender alertas',
    ],
  },
  chef: {
    title: 'Chef',
    subtitle: '',
    actions: ['Consultar stock', 'Revisar disponibilidad', 'Ver alertas de insumos'],
  },
  ayudante_cocina: {
    title: 'Ayudante de cocina',
    subtitle: '',
    actions: ['Registrar entrada', 'Registrar salida', 'Registrar merma', 'Consultar stock', 'Revisar disponibilidad'],
  },
};

function App() {
  // Estados de formularios, sesion, datos cargados y mensajes de pantalla.
  const [form, setForm] = useState(initialForm);
  const [userForm, setUserForm] = useState(initialUserForm);
  const [usuario, setUsuario] = useState(null);
  const [usuarios, setUsuarios] = useState([]);
  const [roles, setRoles] = useState([]);
  const [permisos, setPermisos] = useState([]);
  const [insumos, setInsumos] = useState([]);
  const [entradas, setEntradas] = useState([]);
  const [salidas, setSalidas] = useState([]);
  const [mermas, setMermas] = useState([]);
  const [notificaciones, setNotificaciones] = useState([]);
  const [feriados, setFeriados] = useState([]);
  const [biData, setBiData] = useState(initialBiData);
  const [selectedRoleId, setSelectedRoleId] = useState('');
  const [entradaForm, setEntradaForm] = useState(initialEntradaForm);
  const [stockMinimoForm, setStockMinimoForm] = useState(initialStockMinimoForm);
  const [salidaForm, setSalidaForm] = useState(initialSalidaForm);
  const [mermaForm, setMermaForm] = useState(initialMermaForm);
  const [selectedDemandIndex, setSelectedDemandIndex] = useState(0);
  const [historialVentaFiltro, setHistorialVentaFiltro] = useState('');
  const [activeModule, setActiveModule] = useState('');
  const [error, setError] = useState('');
  const [moduleError, setModuleError] = useState('');
  const [moduleMessage, setModuleMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [savingUser, setSavingUser] = useState(false);
  const [savingEntrada, setSavingEntrada] = useState(false);
  const [savingStockMinimo, setSavingStockMinimo] = useState(false);
  const [savingSalida, setSavingSalida] = useState(false);
  const [savingMerma, setSavingMerma] = useState(false);
  const [runningEtl, setRunningEtl] = useState(false);
  const [syncingFeriados, setSyncingFeriados] = useState(false);
  const [checkingSession, setCheckingSession] = useState(true);
  const [isOnline, setIsOnline] = useState(() => navigator.onLine);
  const [pendingOperations, setPendingOperations] = useState(0);
  const [syncingOffline, setSyncingOffline] = useState(false);
  const [offlineErrors, setOfflineErrors] = useState([]);
  const [offlineMessage, setOfflineMessage] = useState('');
  const refreshStockRef = useRef(null);
  const refreshRunning = useRef(false);

  const dashboard = useMemo(() => dashboards[usuario?.rol] || null, [usuario]);
  const nombreUsuario = useMemo(() => {
    const nombre = usuario?.nombre || '';
    const apellido = usuario?.apellido || '';
    const normalizar = (valor) => String(valor || '').trim().toLowerCase().replaceAll('_', ' ');
    const apellidoNormalizado = normalizar(apellido);
    const apellidoEsRol = [usuario?.rol_nombre, dashboard?.title, usuario?.rol]
      .some((valor) => {
        const rolNormalizado = normalizar(valor);
        return rolNormalizado === apellidoNormalizado || rolNormalizado.includes(apellidoNormalizado);
      });
    return [nombre, apellidoEsRol ? '' : apellido].filter(Boolean).join(' ');
  }, [dashboard, usuario]);
  const isPropietario = usuario?.rol === 'propietario';
  const canEditStockMinimo = ['propietario', 'ayudante_cocina', 'chef'].includes(usuario?.rol);
  // Rol seleccionado para revisar permisos dentro del modulo administrativo.
  const selectedRole = useMemo(
    () => roles.find((rol) => String(rol.id_rol) === String(selectedRoleId)),
    [roles, selectedRoleId],
  );
  // Agrupa permisos por modulo para mostrarlos ordenados en la interfaz.
  const permissionsByModule = useMemo(
    () => permisos.reduce((groups, permiso) => {
      const modulo = permiso.modulo || 'General';
      return {
        ...groups,
        [modulo]: [...(groups[modulo] || []), permiso],
      };
    }, {}),
    [permisos],
  );
  // Insumo elegido al registrar una entrada de compra.
  const selectedInsumo = useMemo(
    () => insumos.find((insumo) => String(insumo.id_insumo) === String(entradaForm.id_insumo)),
    [entradaForm.id_insumo, insumos],
  );
  const opcionesCompra = selectedInsumo?.nombre?.toLowerCase() === 'locoto'
    ? [{ value: 'arroba', label: 'Arroba - 11 kg' }]
    : [
      { value: 'kilo', label: 'Kilo' },
      { value: 'carga', label: 'Carga - 100 kg' },
      { value: 'caja', label: 'Caja - 100 kg' },
    ];
  const entradaConvertida = useMemo(() => {
    // Convierte la compra ingresada a la unidad base que maneja el stock.
    const factor = factoresCompraKg[entradaForm.tipo_compra] || 1;
    const cantidadCompra = Number(entradaForm.cantidad_compra || 0);
    const costoCompra = Number(entradaForm.costo_compra || 0);
    const cantidadKg = cantidadCompra * factor;
    const costoUnitarioKg = factor ? costoCompra / factor : 0;
    const total = cantidadCompra * costoCompra;

    return {
      cantidadKg,
      costoUnitarioKg,
      total,
      factor,
    };
  }, [entradaForm.cantidad_compra, entradaForm.costo_compra, entradaForm.tipo_compra]);
  const salidaPorPlato = useMemo(() => {
    // Calcula los insumos que se descontaran segun plato, tamano y cantidad.
    const receta = recetasPorPlato[salidaForm.plato] || [];
    const factor = factorTamano[salidaForm.tamano] || 1;
    const cantidadPlatos = Number(salidaForm.cantidad_platos || 0);

    return receta.map(([nombre, cantidadBase]) => {
      const insumo = insumos.find((item) => item.nombre.toLowerCase() === nombre.toLowerCase());
      const cantidad = cantidadBase * factor * cantidadPlatos;

      return {
        nombre,
        insumo,
        cantidad,
        disponible: Number(insumo?.cantidad_actual || 0),
      };
    });
  }, [insumos, salidaForm.cantidad_platos, salidaForm.plato, salidaForm.tamano]);
  const precioSalida = useMemo(() => {
    // Obtiene precio unitario y venta estimada del plato seleccionado.
    const precioUnitario = preciosPorPlato[salidaForm.plato]?.[salidaForm.tamano] || 0;
    const cantidadPlatos = Number(salidaForm.cantidad_platos || 0);

    return {
      precioUnitario,
      totalVenta: precioUnitario * cantidadPlatos,
    };
  }, [salidaForm.cantidad_platos, salidaForm.plato, salidaForm.tamano]);
  const totalCompras = useMemo(
    // Indicador rapido del costo acumulado de compras registradas.
    () => entradas.reduce((total, entrada) => total + Number(entrada.total_compra || 0), 0),
    [entradas],
  );
  const disponibilidadProduccion = useMemo(
    // Marca si cada insumo clave tiene stock suficiente para produccion.
    () => insumosProduccion.map((nombre) => {
      const insumo = insumos.find((item) => item.nombre.toLowerCase() === nombre.toLowerCase());

      return {
        nombre,
        insumo,
        disponible: Boolean(insumo && !isStockMinimo(insumo)),
        critico: Boolean(insumo && isStockMinimo(insumo)),
      };
    }),
    [insumos],
  );
  const maxConsumo = useMemo(
    // Valor maximo usado para normalizar barras del reporte de consumo.
    () => Math.max(...(biData.consumo_por_insumo || []).map((item) => Number(item.total || 0)), 1),
    [biData],
  );
  const demandaFuerte = useMemo(
    // Ordena la demanda por dia/franja para mostrar donde se concentra la atencion.
    () => [...(biData.demanda_por_dia_franja || [])]
      .sort((a, b) => Number(b.promedio_platos || 0) - Number(a.promedio_platos || 0))
      .slice(0, 10),
    [biData],
  );
  const coberturaCritica = useMemo(
    // Prioriza los insumos con menor cantidad de días estimados de cobertura.
    () => [...(biData.cobertura_estimada_stock || [])]
      .sort((a, b) => Number(a.cobertura_dias || 0) - Number(b.cobertura_dias || 0))
      .slice(0, 10),
    [biData],
  );
  const tendenciaVentasConsumo = useMemo(
    // Cruza ventas estimadas con consumo en kg para leer variacion real de demanda.
    () => [...(biData.tendencia_ventas_consumo || [])],
    [biData],
  );
  const ultimaTendencia = tendenciaVentasConsumo.at(-1);
  const mesesReporte = useMemo(
    // Resume automaticamente todos los meses que existan en el Data Mart.
    () => {
      const meses = new Map();
      const ensureMes = (year, month, nombre) => {
        const key = `${year}-${String(month).padStart(2, '0')}`;
        const current = meses.get(key) || {
          key,
          anio: year,
          mes: month,
          nombre: nombre || mesesNombre[month - 1] || `Mes ${month}`,
          consumoKg: 0,
          costoConsumido: 0,
          comprasKg: 0,
          costoCompras: 0,
          mermaKg: 0,
          costoMerma: 0,
          ventas: 0,
          utilidad: 0,
          utilidadNeta: 0,
          platos: 0,
          movimientos: 0,
        };
        meses.set(key, current);
        return current;
      };

      (biData.consumo_mensual || []).forEach((item) => {
        const month = Number(item.id_dim_tiempo__mes || 0);
        const year = Number(item.id_dim_tiempo__anio || new Date().getFullYear());
        if (!month) {
          return;
        }
        const mes = ensureMes(year, month, item.id_dim_tiempo__nombre_mes);
        mes.consumoKg = Number(item.total || 0);
        mes.costoConsumido = Number(item.costo || 0);
        mes.movimientos += Number(item.movimientos || 0);
      });

      (biData.compras_mensual || []).forEach((item) => {
        const month = Number(item.id_dim_tiempo__mes || 0);
        const year = Number(item.id_dim_tiempo__anio || new Date().getFullYear());
        if (!month) {
          return;
        }
        const mes = ensureMes(year, month, item.id_dim_tiempo__nombre_mes);
        mes.comprasKg = Number(item.total || 0);
        mes.costoCompras = Number(item.costo || 0);
        mes.movimientos += Number(item.movimientos || 0);
      });

      (biData.merma_mensual || []).forEach((item) => {
        const month = Number(item.id_dim_tiempo__mes || 0);
        const year = Number(item.id_dim_tiempo__anio || new Date().getFullYear());
        if (!month) {
          return;
        }
        const mes = ensureMes(year, month, item.id_dim_tiempo__nombre_mes);
        mes.mermaKg = Number(item.total || 0);
        mes.costoMerma = Number(item.costo || 0);
        mes.movimientos += Number(item.movimientos || 0);
      });

      (biData.ganancias_mensuales || []).forEach((item) => {
        const parts = getDateParts(item.mes);
        if (!parts) {
          return;
        }
        const mes = ensureMes(parts.year, parts.month, mesesNombre[parts.month - 1]);
        mes.ventas = Number(item.ventas || 0);
        mes.utilidad = Number(item.ganancia || 0);
        mes.platos = Number(item.platos || 0);
      });

      return [...meses.values()]
        .map((item) => ({ ...item, utilidadNeta: item.utilidad - item.costoMerma }))
        .sort((a, b) => (a.anio - b.anio) || (a.mes - b.mes));
    },
    [biData],
  );
  const historialVentasFiltrado = useMemo(
    () => {
      const filtro = historialVentaFiltro.trim().toLowerCase();
      const historial = [...(biData.ganancias_diarias || [])].sort((a, b) =>
        String(a.fecha || '').localeCompare(String(b.fecha || '')),
      );

      if (!filtro) {
        return historial;
      }

      return historial.filter((item) => {
        const texto = [
          String(item.fecha || ''),
          formatDateOnly(item.fecha),
          monthNameFromDate(item.fecha),
          formatCantidad(item.platos),
          formatMoney(item.ventas),
        ].join(' ').toLowerCase();
        return texto.includes(filtro);
      });
    },
    [biData.ganancias_diarias, historialVentaFiltro],
  );
  const platoLimitante = biData.platos_disponibles?.[0];
  const stockEnRiesgo = useMemo(
    // Cuenta insumos cuyo stock actual esta por debajo o cerca del minimo definido.
    () => (biData.stock_actual || []).filter((insumo) => {
      const minimo = Number(insumo.stock_minimo || 0);
      const actual = Number(insumo.stock__cantidad_actual || 0);
      return minimo > 0 && actual <= minimo * 1.25;
    }),
    [biData],
  );
  const porcentajeStockRiesgo = useMemo(
    // Porcentaje usado por la dona de stock frente al minimo.
    () => {
      const total = biData.stock_actual?.length || 0;
      return total ? Math.round((stockEnRiesgo.length / total) * 100) : 0;
    },
    [biData, stockEnRiesgo],
  );
  const totalPlatosDisponibles = useMemo(
    // Suma la capacidad calculada por receta para mostrar una lectura rapida de atencion.
    () => (biData.platos_disponibles || []).reduce(
      (total, item) => total + Number(item.platos_enteros_disponibles || 0),
      0,
    ),
    [biData],
  );
  const demandaPico = demandaFuerte?.[selectedDemandIndex] || demandaFuerte?.[0];
  const demandaDetalleHorario = useMemo(
    () => {
      if (!demandaPico) {
        return [];
      }

      return (biData.demanda_por_dia_franja || [])
        .filter((item) =>
          item.nombre_dia === demandaPico.nombre_dia
          && item.franja_horaria === demandaPico.franja_horaria,
        )
        .sort((a, b) => Number(b.promedio_platos || 0) - Number(a.promedio_platos || 0));
    },
    [biData.demanda_por_dia_franja, demandaPico],
  );
  const totalMermaKg = Number(biData.resumen?.total_mermas || 0);
  const totalMermaCosto = Number(biData.resumen?.costo_merma || 0);
  const kpisDecision = biData.kpis_decision || [];
  const kpiStock = kpisDecision.find((item) => item.codigo === 'stock_minimo');
  const kpiPlatos = kpisDecision.find((item) => item.codigo === 'platos_disponibles');
  const kpiDemanda = kpisDecision.find((item) => item.codigo === 'demanda_franja');
  const kpiTendencia = kpisDecision.find((item) => item.codigo === 'tendencia_ventas_consumo');
  const kpiCobertura = kpisDecision.find((item) => item.codigo === 'cobertura_riesgo');
  const kpiMerma = kpisDecision.find((item) => item.codigo === 'merma_insumo');
  const kpiMeta = kpisDecision.find((item) => item.codigo === 'meta_ventas');
  const analisisComplementarios = biData.analisis_complementarios || {};
  const decisionKpis = useMemo(
    () => [
      kpiStock,
      kpiPlatos,
      kpiDemanda,
      kpiTendencia,
      kpiCobertura,
      kpiMerma,
      kpiMeta,
    ],
    [kpiCobertura, kpiDemanda, kpiMerma, kpiMeta, kpiPlatos, kpiStock, kpiTendencia],
  );
  const stockActualChartData = useMemo(
    () => (biData.stock_actual || []).map((insumo) => ({
      nombre: insumo.nombre,
      actual: Number(insumo.stock__cantidad_actual || 0),
      minimo: Number(insumo.stock_minimo || 0),
      unidad: insumo.id_unidad__nombre_unidad || 'kg',
    })),
    [biData.stock_actual],
  );
  const stockVsMinimoOption = useMemo(() => ({
    color: ['#1f6f8b', '#c3423f'],
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    legend: {
      top: 0,
      textStyle: chartTextStyle,
    },
    grid: gridStyle,
    xAxis: {
      type: 'category',
      data: stockActualChartData.map((item) => item.nombre),
      axisLabel: { ...chartTextStyle, rotate: 28 },
    },
    yAxis: {
      type: 'value',
      axisLabel: { ...chartTextStyle, formatter: '{value} kg' },
      splitLine: { lineStyle: { color: '#e8efeb' } },
    },
    series: [
      {
        name: 'Stock actual',
        type: 'bar',
        data: stockActualChartData.map((item) => item.actual),
        itemStyle: { borderRadius: [6, 6, 0, 0] },
      },
      {
        name: 'Stock minimo',
        type: 'bar',
        data: stockActualChartData.map((item) => item.minimo),
        itemStyle: { borderRadius: [6, 6, 0, 0] },
      },
    ],
  }), [stockActualChartData]);
  const stockRiskGaugeOption = useMemo(() => ({
    color: businessChartPalette,
    tooltip: tooltipStyle,
    series: [{
      name: 'Riesgo',
      type: 'gauge',
      radius: '86%',
      center: ['50%', '56%'],
      min: 0,
      max: 100,
      progress: { show: true, width: 14 },
      axisLine: { lineStyle: { width: 14, color: [[0.35, '#2f8f6f'], [0.7, '#d59b2d'], [1, '#c3423f']] } },
      axisTick: { show: false },
      splitLine: { length: 8, lineStyle: { color: '#9ca3af' } },
      axisLabel: { color: '#66736c', distance: 18 },
      pointer: { width: 5 },
      title: {
        offsetCenter: [0, '62%'],
        color: '#66736c',
        fontSize: 13,
        fontWeight: 700,
      },
      detail: {
        valueAnimation: true,
        formatter: (value) => `${Math.round(value)}%`,
        offsetCenter: [0, '35%'],
        color: '#30413b',
        fontSize: 28,
        fontWeight: 900,
      },
      data: [{ value: porcentajeStockRiesgo, name: 'Insumos en riesgo' }],
    }],
  }), [porcentajeStockRiesgo]);
  const platosDisponiblesOption = useMemo(() => ({
    color: ['#2f8f6f'],
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (items) => {
        const item = items?.[0];
        const detalle = (biData.platos_disponibles || []).find((plato) => plato.plato === item?.name);
        return `${item?.name || 'Plato'}<br/>Disponibles: ${formatCantidad(item?.value)}<br/>Limita: ${detalle?.insumo_limitante || 'Sin referencia'}`;
      },
    },
    grid: gridStyle,
    xAxis: {
      type: 'category',
      data: (biData.platos_disponibles || []).map((item) => item.plato),
      axisLabel: chartTextStyle,
    },
    yAxis: {
      type: 'value',
      axisLabel: chartTextStyle,
      splitLine: { lineStyle: { color: '#e8efeb' } },
    },
    series: [{
      name: 'Platos disponibles',
      type: 'bar',
      data: (biData.platos_disponibles || []).map((item) => Number(item.platos_enteros_disponibles || 0)),
      itemStyle: { borderRadius: [6, 6, 0, 0] },
    }],
  }), [biData.platos_disponibles]);
  const demandaFranjaOption = useMemo(() => ({
    color: ['#1f6f8b'],
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (items) => {
        const item = items?.[0];
        return `${item?.axisValue || 'Horario'}<br/>Plato vendido: ${item?.data?.plato || 'Sin plato'}<br/>Promedio: ${formatCantidad(item?.value)} platos`;
      },
    },
    grid: { ...gridStyle, left: 56 },
    xAxis: {
      type: 'category',
      data: demandaFuerte.map((item) => `${item.nombre_dia?.slice(0, 3) || ''} ${item.franja_horaria}`),
      axisLabel: { ...chartTextStyle, rotate: 32 },
    },
    yAxis: {
      type: 'value',
      name: 'Platos',
      nameTextStyle: chartTextStyle,
      axisLabel: chartTextStyle,
      splitLine: { lineStyle: { color: '#e8efeb' } },
    },
    series: [{
      name: 'Demanda promedio',
      type: 'bar',
      data: demandaFuerte.map((item) => ({
        value: Number(item.promedio_platos || 0),
        plato: item.plato,
      })),
      itemStyle: { borderRadius: [6, 6, 0, 0] },
    }],
  }), [demandaFuerte]);
  const tendenciaVentasOption = useMemo(() => ({
    color: ['#2f8f6f', '#c3423f'],
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      formatter: (items) => items.map((item) => {
        const value = item.seriesName === 'Ventas' ? formatMoney(item.value) : `${formatCantidad(item.value)} kg`;
        return `${item.marker}${item.seriesName}: ${value}`;
      }).join('<br/>'),
    },
    legend: {
      top: 0,
      textStyle: chartTextStyle,
    },
    grid: { ...gridStyle, left: 58, right: 58 },
    xAxis: {
      type: 'category',
      data: tendenciaVentasConsumo.map((item) => new Date(item.semana).toLocaleDateString('es-BO')),
      axisLabel: { ...chartTextStyle, rotate: 25 },
    },
    yAxis: [
      {
        type: 'value',
        name: 'Bs',
        nameTextStyle: chartTextStyle,
        axisLabel: { ...chartTextStyle, formatter: '{value}' },
        splitLine: { lineStyle: { color: '#e8efeb' } },
      },
      {
        type: 'value',
        name: 'kg',
        nameTextStyle: chartTextStyle,
        axisLabel: chartTextStyle,
      },
    ],
    series: [
      {
        name: 'Ventas',
        type: 'line',
        smooth: true,
        symbolSize: 8,
        data: tendenciaVentasConsumo.map((item) => Number(item.ventas || 0)),
        areaStyle: { opacity: 0.08 },
      },
      {
        name: 'Consumo',
        type: 'bar',
        yAxisIndex: 1,
        data: tendenciaVentasConsumo.map((item) => Number(item.consumo || 0)),
        itemStyle: { borderRadius: [6, 6, 0, 0] },
      },
    ],
  }), [tendenciaVentasConsumo]);
  const coberturaOption = useMemo(() => ({
    color: ['#d59b2d'],
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      formatter: (items) => {
        const item = items?.[0];
        const detalle = coberturaCritica.find((insumo) => insumo.insumo === item?.name);
        return `${item?.name || 'Insumo'}<br/>Cobertura: ${Number(item?.value || 0).toFixed(1)} dias<br/>Consumo prom.: ${formatCantidad(detalle?.consumo_promedio_diario)} kg/dia`;
      },
    },
    grid: { left: 110, right: 24, top: 24, bottom: 28 },
    xAxis: {
      type: 'value',
      axisLabel: { ...chartTextStyle, formatter: '{value} d' },
      splitLine: { lineStyle: { color: '#e8efeb' } },
    },
    yAxis: {
      type: 'category',
      data: coberturaCritica.map((item) => item.insumo),
      axisLabel: chartTextStyle,
    },
    series: [{
      name: 'Cobertura',
      type: 'bar',
      data: coberturaCritica.map((item) => ({
        value: Number(item.cobertura_dias || 0),
        itemStyle: {
          color: Number(item.cobertura_dias || 0) <= 2 ? '#c3423f' : Number(item.cobertura_dias || 0) <= 5 ? '#d59b2d' : '#2f8f6f',
        },
      })),
      itemStyle: { borderRadius: [0, 6, 6, 0] },
    }],
  }), [coberturaCritica]);
  const mermaOption = useMemo(() => {
    const mermaData = (biData.merma_por_insumo?.length ? biData.merma_por_insumo : [{ id_dim_insumo__nombre: 'Sin merma', cantidad: 0 }])
      .map((item) => ({ name: item.id_dim_insumo__nombre, value: Number(item.cantidad || 0) }));

    return {
      color: businessChartPalette,
      tooltip: {
        ...tooltipStyle,
        trigger: 'item',
        formatter: '{b}<br/>{c} kg ({d}%)',
      },
      legend: {
        orient: 'vertical',
        right: 8,
        top: 16,
        textStyle: chartTextStyle,
      },
      series: [{
        name: 'Merma',
        type: 'pie',
        radius: ['48%', '72%'],
        center: ['38%', '54%'],
        avoidLabelOverlap: true,
        label: { color: '#30413b' },
        data: mermaData,
      }],
    };
  }, [biData.merma_por_insumo]);
  const metaVentasOption = useMemo(() => ({
    color: businessChartPalette,
    tooltip: tooltipStyle,
    series: [{
      name: 'Meta',
      type: 'gauge',
      radius: '86%',
      center: ['50%', '56%'],
      min: 0,
      max: 100,
      progress: { show: true, width: 16 },
      axisLine: { lineStyle: { width: 16, color: [[0.6, '#c3423f'], [0.9, '#d59b2d'], [1, '#2f8f6f']] } },
      axisTick: { show: false },
      splitLine: { length: 8, lineStyle: { color: '#9ca3af' } },
      axisLabel: { color: '#66736c', distance: 18 },
      pointer: { width: 5 },
      title: {
        offsetCenter: [0, '62%'],
        color: '#66736c',
        fontSize: 13,
        fontWeight: 700,
      },
      detail: {
        valueAnimation: true,
        formatter: (value) => `${Number(value || 0).toFixed(1)}%`,
        offsetCenter: [0, '35%'],
        color: '#30413b',
        fontSize: 28,
        fontWeight: 900,
      },
      data: [{ value: Number(Math.min(Number(kpiMeta?.valor || 0), 100).toFixed(1)), name: 'Cumplimiento' }],
    }],
  }), [kpiMeta]);
  const costosOption = useMemo(() => ({
    color: ['#1f6f8b', '#c3423f'],
    tooltip: {
      ...tooltipStyle,
      trigger: 'axis',
      formatter: (items) => items.map((item) =>
        `${item.marker}${item.seriesName}: ${item.seriesName === 'Costo compras' ? formatMoney(item.value) : `${formatCantidad(item.value)} kg`}`,
      ).join('<br/>'),
    },
    legend: { top: 0, textStyle: chartTextStyle },
    grid: { ...gridStyle, left: 60, right: 58 },
    xAxis: {
      type: 'category',
      data: (biData.compras_mensual || []).map((item) => item.id_dim_tiempo__nombre_mes || item.id_dim_tiempo__mes),
      axisLabel: chartTextStyle,
    },
    yAxis: [
      {
        type: 'value',
        name: 'Bs',
        nameTextStyle: chartTextStyle,
        axisLabel: chartTextStyle,
        splitLine: { lineStyle: { color: '#e8efeb' } },
      },
      {
        type: 'value',
        name: 'kg',
        nameTextStyle: chartTextStyle,
        axisLabel: chartTextStyle,
      },
    ],
    series: [
      {
        name: 'Costo compras',
        type: 'bar',
        data: (biData.compras_mensual || []).map((item) => Number(item.costo || 0)),
        itemStyle: { borderRadius: [6, 6, 0, 0] },
      },
      {
        name: 'Entradas kg',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbolSize: 8,
        data: (biData.compras_mensual || []).map((item) => Number(item.total || 0)),
      },
    ],
  }), [biData.compras_mensual]);

  useEffect(() => {
    // Recupera la sesion guardada al recargar la pagina.
    const token = localStorage.getItem('token');

    if (!token) {
      setCheckingSession(false);
      return;
    }

    if (!navigator.onLine) {
      const cachedUser = readOfflineUser();
      if (cachedUser) {
        setUsuario(cachedUser);
      } else {
        localStorage.removeItem('token');
      }
      setCheckingSession(false);
      return;
    }

    // Si existe token guardado, se valida con el backend antes de mostrar la sesion.
    api
      .get('/usuarios/perfil/')
      .then(({ data }) => {
        setUsuario(data.usuario);
        localStorage.setItem('chillamicito:offline-user', JSON.stringify(data.usuario));
      })
      .catch((requestError) => {
        const cachedUser = isNetworkFailure(requestError) ? readOfflineUser() : null;
        if (cachedUser) {
          setUsuario(cachedUser);
        } else {
          localStorage.removeItem('token');
          localStorage.removeItem('chillamicito:offline-user');
        }
      })
      .finally(() => setCheckingSession(false));
  }, []);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  useEffect(() => {
    // Abre el WebSocket para recibir alertas nuevas sin refrescar la pagina.
    if (!usuario) {
      return undefined;
    }

    const apiUrl = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api';
    const apiBase = new URL(apiUrl);
    const protocol = apiBase.protocol === 'https:' ? 'wss' : 'ws';
    const socketUrl = `${protocol}://${apiBase.host}/ws/notificaciones/`;
    let socket;
    let reconnectTimer;
    let shouldReconnect = true;

    const connectSocket = () => {
      socket = new WebSocket(socketUrl);

      socket.onmessage = (event) => {
        const notificacion = JSON.parse(event.data);

        if (notificacion.evento === 'movimiento_stock') {
          setModuleMessage(notificacion.mensaje);
          refreshStockRef.current();
          return;
        }

        setNotificaciones((current) => {
          if (current.some((item) => item.id_notificacion === notificacion.id_notificacion)) {
            return current;
          }

          return [notificacion, ...current];
        });
        setModuleMessage(`Nueva alerta: ${notificacion.mensaje}`);
      };

      socket.onerror = () => {
        socket.close();
      };

      socket.onclose = () => {
        if (!shouldReconnect) {
          return;
        }

        reconnectTimer = window.setTimeout(connectSocket, 3000);
      };
    };

    connectSocket();

    return () => {
      shouldReconnect = false;
      window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [usuario]);

  const applyStockResult = (result, token) => {
    if (localStorage.getItem('token') !== token) return;
    if ([401, 403].includes(result.failure?.response?.status)) {
      setOfflineMessage('La sesion o sus permisos cambiaron. Inicia sesion nuevamente.');
      if (result.failure.response.status === 401) handleLogout();
      return;
    }
    if (result.data) {
      setInsumos(result.data.insumos || []);
      setEntradas(result.data.entradas || []);
      setSalidas(result.data.salidas || []);
      setMermas(result.data.mermas || []);
      setNotificaciones(result.data.notificaciones || []);
    }
    setPendingOperations(result.operations.length);
    setOfflineErrors(result.operations.filter((item) => item.status === 'error'));
    if (result.failure) {
      setOfflineMessage(errorMessage(result.failure));
      if (isNetworkFailure(result.failure)) setIsOnline(false);
    } else {
      setOfflineMessage('');
      setIsOnline(navigator.onLine);
    }
  };

  const refreshStock = async (retry = false) => {
    if (!usuario || refreshRunning.current) return null;
    const token = localStorage.getItem('token');
    refreshRunning.current = true;
    setSyncingOffline(true);
    try {
      const result = await stockClient.sync(usuario, token, retry);
      applyStockResult(result, token);
      return result;
    } catch (requestError) {
      if (localStorage.getItem('token') === token) setOfflineMessage(errorMessage(requestError));
      return null;
    } finally {
      refreshRunning.current = false;
      setSyncingOffline(false);
    }
  };
  refreshStockRef.current = refreshStock;

  useEffect(() => {
    if (!usuario) return undefined;
    refreshStockRef.current();
    const retry = () => refreshStockRef.current();
    window.addEventListener('online', retry);
    const timer = window.setInterval(retry, 30000);
    return () => {
      window.removeEventListener('online', retry);
      window.clearInterval(timer);
    };
  }, [usuario]);

  const loadStockView = async (moduleName) => {
    setModuleError('');
    try {
      const token = localStorage.getItem('token');
      const result = await stockClient.sync(usuario, token);
      applyStockResult(result, token);
      if (localStorage.getItem('token') !== token || [401, 403].includes(result.failure?.response?.status)) return;
      if (!result.data) throw new Error('Primero carga los datos con conexion.');
      setActiveModule(moduleName);
    } catch (requestError) {
      setModuleError(errorMessage(requestError));
    }
  };

  const handleChange = ({ target }) => {
    // Actualiza usuario o contrasena del formulario de login.
    setForm((currentForm) => ({
      ...currentForm,
      [target.name]: target.value,
    }));
  };

  const handleUserChange = ({ target }) => {
    // Actualiza campos del formulario de gestion de usuarios.
    const value = target.type === 'checkbox' ? target.checked : target.value;
    setUserForm((currentForm) => ({
      ...currentForm,
      [target.name]: value,
    }));
  };

  const loadUserManagement = async () => {
    // Carga usuarios y roles para el modulo del propietario.
    setModuleError('');

    try {
      const [rolesResponse, usuariosResponse] = await Promise.all([
        api.get('/usuarios/roles/'),
        api.get('/usuarios/gestion/'),
      ]);

      setRoles(rolesResponse.data);
      setUsuarios(usuariosResponse.data);
      setActiveModule('usuarios');
    } catch (requestError) {
      setModuleError(requestError.response?.data?.detail || 'No se pudo cargar la gestión de usuarios.');
    }
  };

  const loadRoleManagement = async () => {
    // Carga roles y permisos para revisar accesos por perfil.
    setModuleError('');

    try {
      const [rolesResponse, permisosResponse] = await Promise.all([
        api.get('/usuarios/roles/'),
        api.get('/usuarios/permisos/'),
      ]);
      const firstRole = rolesResponse.data[0];

      setRoles(rolesResponse.data);
      setPermisos(permisosResponse.data);
      setSelectedRoleId(firstRole ? String(firstRole.id_rol) : '');
      setActiveModule('roles');
    } catch (requestError) {
      setModuleError(requestError.response?.data?.detail || 'No se pudo cargar la gestión de roles.');
    }
  };

  const loadEntradaModule = () => loadStockView('entradas');
  const loadStockModule = () => loadStockView('stock');
  const loadDisponibilidadModule = () => loadStockView('disponibilidad');
  const loadAlertasModule = () => loadStockView('alertas');
  const loadSalidaModule = () => loadStockView('salidas');
  const loadMermaModule = () => loadStockView('mermas');

  const loadBiModule = async (moduleName) => {
    // Recalcula el Data Mart antes de mostrar reportes o dashboards para evitar datos antiguos.
    setModuleError('');
    setModuleMessage('');

    try {
      await api.post('/usuarios/bi/etl/');
      const dashboardResponse = await api.get('/usuarios/bi/dashboard/');

      setBiData(dashboardResponse.data);
      setActiveModule(moduleName);
    } catch (requestError) {
      setModuleError(requestError.response?.data?.detail || 'No se pudo cargar la informacion BI.');
    }
  };

  const refreshBiModule = async (moduleName) => {
    // Ejecuta el ETL solo cuando se presiona Actualizar Data Mart.
    setModuleError('');
    setModuleMessage('');
    setRunningEtl(true);

    try {
      await api.post('/usuarios/bi/etl/');
      const dashboardResponse = await api.get('/usuarios/bi/dashboard/');

      setBiData(dashboardResponse.data);
      setActiveModule(moduleName);
    } catch (requestError) {
      setModuleError(requestError.response?.data?.detail || 'No se pudo actualizar la informacion BI.');
    } finally {
      setRunningEtl(false);
    }
  };

  const downloadMonthlyReport = (report) => {
    try {
      const doc = createMonthlyReportPdf(report, { formatMoney, formatCantidad });
      doc.save(monthlyReportFilename(report));
    } catch {
      setModuleError('No se pudo generar el PDF. Intenta nuevamente.');
    }
  };

  const loadFeriadosModule = async () => {
    // Sincroniza Nager.Date y muestra el calendario de planificacion.
    setModuleError('');
    setModuleMessage('');
    setSyncingFeriados(true);

    try {
      const year = new Date().getFullYear();
      const response = await api.post('/usuarios/feriados/', { anio: year, pais: 'BO' });
      setFeriados(response.data.feriados);
      setActiveModule('feriados');
      setModuleMessage(response.data.mensaje);
    } catch (requestError) {
      try {
        const year = new Date().getFullYear();
        const response = await api.get(`/usuarios/feriados/?anio=${year}&pais=BO`);
        setFeriados(response.data);
        setActiveModule('feriados');
        setModuleError('No se pudo sincronizar; se muestran feriados guardados.');
      } catch {
        setModuleError(requestError.response?.data?.detail || 'No se pudieron cargar los feriados.');
      }
    } finally {
      setSyncingFeriados(false);
    }
  };

  const handleSubmit = async (event) => {
    // Inicia sesion contra el backend y guarda el token localmente.
    event.preventDefault();
    setError('');
    setLoading(true);

    try {
      const { data } = await api.post('/usuarios/login/', form);
      localStorage.setItem('token', data.token);
      localStorage.setItem('chillamicito:offline-user', JSON.stringify(data.usuario));
      setUsuario(data.usuario);
      setForm(initialForm);
    } catch (requestError) {
      setError(requestError.response?.data?.detail || 'No se pudo iniciar sesión.');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    // Limpia datos sensibles y regresa a la pantalla de login.
    localStorage.removeItem('token');
    localStorage.removeItem('chillamicito:offline-user');
    setUsuario(null);
    setPendingOperations(0);
    setOfflineErrors([]);
    setOfflineMessage('');
    setUsuarios([]);
    setRoles([]);
    setPermisos([]);
    setInsumos([]);
    setEntradas([]);
    setSalidas([]);
    setMermas([]);
    setNotificaciones([]);
    setFeriados([]);
    setBiData(initialBiData);
    setSelectedRoleId('');
    setActiveModule('');
    setUserForm(initialUserForm);
    setEntradaForm(initialEntradaForm);
    setSalidaForm(initialSalidaForm);
    setMermaForm(initialMermaForm);
  };

  const handleModuleClick = (action) => {
    // Traduce cada boton del dashboard al modulo que debe abrirse.
    setModuleMessage('');
    setModuleError('');

    if (action === 'Gestionar usuarios' && isPropietario) {
      loadUserManagement();
      return;
    }

    if (action === 'Gestionar roles y permisos' && isPropietario) {
      loadRoleManagement();
      return;
    }

    if (action === 'Registrar entrada') {
      loadEntradaModule();
      return;
    }

    if (action === 'Consultar stock' || action === 'Revisar stock') {
      loadStockModule();
      return;
    }

    if (action === 'Revisar disponibilidad') {
      loadDisponibilidadModule();
      return;
    }

    if (action === 'Registrar salida') {
      loadSalidaModule();
      return;
    }

    if (action === 'Registrar merma') {
      loadMermaModule();
      return;
    }

    if (action === 'Atender alertas' || action === 'Ver alertas de insumos') {
      loadAlertasModule();
      return;
    }

    if (action === 'Consultar feriados') {
      loadFeriadosModule();
      return;
    }

    if (action === 'Ver reportes' && isPropietario) {
      loadBiModule('reportes');
      return;
    }

    if (action === 'Ver dashboards' && isPropietario) {
      loadBiModule('dashboards');
      return;
    }

    setActiveModule('');
    setModuleMessage('Este modulo queda pendiente para la siguiente etapa.');
  };

  const handleEntradaChange = ({ target }) => {
    // Actualiza el formulario de entrada de insumos.
    const nextValue = target.value;
    const nextInsumo = target.name === 'id_insumo'
      ? insumos.find((insumo) => String(insumo.id_insumo) === String(nextValue))
      : null;

    setEntradaForm((currentForm) => ({
      ...currentForm,
      [target.name]: nextValue,
      ...(nextInsumo?.nombre?.toLowerCase() === 'locoto' ? { tipo_compra: 'arroba' } : {}),
      ...(nextInsumo && nextInsumo.nombre?.toLowerCase() !== 'locoto' && currentForm.tipo_compra === 'arroba'
        ? { tipo_compra: 'kilo' }
        : {}),
    }));
  };

  const handleMermaChange = ({ target }) => {
    // Actualiza el formulario de merma manual.
    const { name, value } = target;
    setMermaForm((currentForm) => ({
      ...currentForm,
      [name]: value,
    }));
  };

  const handleStockMinimoChange = ({ target }) => {
    // Actualiza solo el minimo; este valor se guarda en Insumo.stock_minimo.
    setStockMinimoForm((currentForm) => ({
      ...currentForm,
      [target.name]: target.value,
    }));
  };

  const handleSalidaChange = ({ target }) => {
    // Actualiza el formulario de salida de platos/insumos.
    setSalidaForm((currentForm) => ({
      ...currentForm,
      [target.name]: target.value,
    }));
  };

  const handleEditUser = (selectedUser) => {
    // Carga los datos de un usuario en el formulario para editarlo.
    setUserForm({
      id_usuario: selectedUser.id_usuario,
      nombre: selectedUser.nombre,
      apellido: selectedUser.apellido || '',
      username: selectedUser.username,
      correo: selectedUser.correo || '',
      id_rol: String(selectedUser.id_rol),
      estado: selectedUser.estado,
      password: '',
    });
    setModuleMessage('');
    setModuleError('');
  };

  const handleCancelUserEdit = () => {
    // Limpia el formulario y cancela la edicion.
    setUserForm(initialUserForm);
    setModuleMessage('');
    setModuleError('');
  };

  const handleEditStockMinimo = (insumo) => {
    // Carga el insumo seleccionado para cambiar el nivel minimo usado en validaciones.
    setStockMinimoForm({
      id_insumo: insumo.id_insumo,
      nombre: insumo.nombre,
      unidad: insumo.unidad_abreviatura || insumo.unidad,
      stock_minimo: insumo.stock_minimo,
    });
    setModuleMessage('');
    setModuleError('');
  };

  const handleCancelStockMinimoEdit = () => {
    // Limpia la edicion sin cambiar el stock actual ni el minimo guardado.
    setStockMinimoForm(initialStockMinimoForm);
    setModuleMessage('');
    setModuleError('');
  };

  const handleSaveUser = async (event) => {
    // Crea o actualiza usuarios desde el panel del propietario.
    event.preventDefault();
    setSavingUser(true);
    setModuleError('');
    setModuleMessage('');

    const payload = {
      nombre: userForm.nombre,
      apellido: userForm.apellido,
      username: userForm.username,
      correo: userForm.correo,
      id_rol: Number(userForm.id_rol),
      estado: userForm.estado,
    };

    if (userForm.password) {
      payload.password = userForm.password;
    }

    try {
      if (userForm.id_usuario) {
        await api.put(`/usuarios/gestion/${userForm.id_usuario}/`, payload);
        setModuleMessage('Usuario actualizado correctamente.');
      } else {
        await api.post('/usuarios/gestion/', payload);
        setModuleMessage('Usuario creado correctamente.');
      }

      setUserForm(initialUserForm);
      const { data } = await api.get('/usuarios/gestion/');
      setUsuarios(data);
    } catch (requestError) {
      const detail = requestError.response?.data;
      setModuleError(
        typeof detail === 'string'
          ? detail
          : detail?.detail || 'No se pudo guardar el usuario. Revisa los datos.',
      );
    } finally {
      setSavingUser(false);
    }
  };

  const handleSelectRole = (rol) => {
    // Selecciona un rol para mostrar sus permisos asignados.
    setSelectedRoleId(String(rol.id_rol));
    setModuleMessage('');
    setModuleError('');
  };

  const saveMovement = async (kind, payload, setSaving, resetForm) => {
    const token = localStorage.getItem('token');
    setSaving(true);
    setModuleError('');
    setModuleMessage('');
    try {
      const result = await stockClient.save(usuario, token, kind, payload);
      if (localStorage.getItem('token') !== token) return;
      applyStockResult(result, token);
      resetForm();
      setModuleMessage(result.operations.length
        ? 'Movimiento guardado en este dispositivo, pendiente de confirmacion.'
        : 'Movimiento registrado y stock actualizado.');
    } catch (requestError) {
      setModuleError(errorMessage(requestError));
    } finally {
      setSaving(false);
    }
  };

  const handleSaveEntrada = async (event) => {
    event.preventDefault();
    const observacion = [
      entradaForm.observacion,
      `Compra registrada: ${formatCantidad(entradaForm.cantidad_compra)} ${labelsCompra[entradaForm.tipo_compra]}(s)`,
      `Equivalencia: 1 ${labelsCompra[entradaForm.tipo_compra]} = ${entradaConvertida.factor} kg`,
    ].filter(Boolean).join(' | ');
    await saveMovement('entrada', {
      observacion,
      detalles: [{
        id_insumo: Number(entradaForm.id_insumo),
        cantidad: Number(entradaConvertida.cantidadKg.toFixed(3)),
        costo_unitario: Number(entradaConvertida.costoUnitarioKg.toFixed(2)),
      }],
    }, setSavingEntrada, () => setEntradaForm(initialEntradaForm));
  };

  const handleSaveStockMinimo = async (event) => {
    // Guarda el nuevo stock minimo en el insumo; las alertas lo usan desde ese campo.
    event.preventDefault();
    if (!stockMinimoForm.id_insumo) {
      return;
    }
    if (pendingOperations) {
      setModuleError('Sincroniza los movimientos pendientes antes de cambiar el minimo.');
      return;
    }

    setSavingStockMinimo(true);
    setModuleError('');
    setModuleMessage('');

    try {
      await api.patch(`/usuarios/stock/insumos/${stockMinimoForm.id_insumo}/`, {
        stock_minimo: Number(stockMinimoForm.stock_minimo),
      });

      await refreshStock();
      setStockMinimoForm(initialStockMinimoForm);
      setModuleMessage('Stock minimo actualizado correctamente.');
    } catch (requestError) {
      const detail = requestError.response?.data;
      setModuleError(detail?.stock_minimo?.[0] || detail?.detail || 'No se pudo actualizar el stock minimo.');
    } finally {
      setSavingStockMinimo(false);
    }
  };

  const handleSaveSalida = async (event) => {
    event.preventDefault();
    const missing = salidaPorPlato.find((item) => !item.insumo);
    if (missing) {
      setModuleError(`Falta registrar el insumo ${missing.nombre}.`);
      return;
    }
    await saveMovement('salida', {
      motivo: `${salidaForm.cantidad_platos} ${salidaForm.tamano}(s) de Pique ${salidaForm.plato}`,
      observacion: salidaForm.observacion,
      plato: salidaForm.plato,
      tamano: salidaForm.tamano,
      cantidad_platos: Number(salidaForm.cantidad_platos),
      precio_unitario: precioSalida.precioUnitario,
      total_venta_estimado: precioSalida.totalVenta,
      detalles: salidaPorPlato.map((item) => ({
        id_insumo: Number(item.insumo.id_insumo), cantidad: Number(item.cantidad.toFixed(3)),
      })),
    }, setSavingSalida, () => setSalidaForm(initialSalidaForm));
  };

  const handleSaveMerma = async (event) => {
    event.preventDefault();
    await saveMovement('merma', {
      id_insumo: Number(mermaForm.id_insumo),
      cantidad: Number(mermaForm.cantidad),
      motivo: mermaForm.motivo,
      observacion: mermaForm.observacion,
    }, setSavingMerma, () => setMermaForm(initialMermaForm));
  };

  if (checkingSession) {
    // Pantalla breve mientras se valida si existe una sesion guardada.
    return (
      <main className="page">
        <p className="status">Cargando sesión...</p>
      </main>
    );
  }

  if (usuario && dashboard) {
    // Vista principal despues del login: muestra panel segun rol y modulo activo.
    return (
      <main className="app-shell">
        <header className="topbar">
          <div className="topbar-brand">
            <span className="brand-flame" aria-hidden="true">
              CH
              <span className={`brand-connection-dot ${isOnline ? 'online' : 'offline'}`} />
            </span>
            <div>
              <span className="eyebrow">Sesión activa</span>
              <h1>{dashboard.title}</h1>
            </div>
          </div>
          <div className="topbar-center" aria-hidden="true">
            <strong>Chillamicito</strong>
          </div>
          <div className="user-box">
            <span className="avatar-badge" aria-hidden="true">{usuario.nombre?.[0] || 'U'}</span>
            <div>
              <strong>{nombreUsuario}</strong>
            </div>
            <button type="button" onClick={handleLogout}>Cerrar sesión</button>
          </div>
        </header>

        <section className="workspace">
          {pendingOperations > 0 && <p role="status">Stock local provisional: {pendingOperations} movimiento(s) pendiente(s) de confirmacion.</p>}
          {offlineMessage && <p className="error" role="alert">{offlineMessage}</p>}
          {pendingOperations > 0 && (
            <button type="button" className="secondary-button" disabled={!isOnline || syncingOffline} onClick={() => refreshStock(true)}>
              {syncingOffline ? 'Sincronizando...' : 'Reintentar pendientes'}
            </button>
          )}
          {offlineErrors.map((operation) => (
            <p className="error" key={operation.id}>
              {operation.kind}: {operation.error}
              {operation.canDiscard && <button type="button" onClick={async () => {
                if (!window.confirm('Descartar este movimiento rechazado?')) return;
                const token = localStorage.getItem('token');
                try {
                  applyStockResult(await stockClient.discard(usuario, operation.id), token);
                  await refreshStock();
                } catch (requestError) { setOfflineMessage(errorMessage(requestError)); }
              }}>Descartar rechazado</button>}
            </p>
          ))}
          <section className="module-hero">
            <div>
              <span className="eyebrow">Tradición de mi llajta</span>
              <h2>Chillamicito</h2>
            </div>
          </section>

          <div className="module-list">
            {dashboard.actions.map((action) => (
              <button className="module-button" type="button" key={action} onClick={() => handleModuleClick(action)}>
                {action}
              </button>
            ))}
          </div>

          {activeModule === 'usuarios' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Propietario</span>
                  <h2>Gestionar usuarios</h2>
                  <p>Administra datos, rol y estado de acceso.</p>
                </div>
                <button type="button" className="secondary-button" onClick={handleCancelUserEdit}>
                  Nuevo usuario
                </button>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <form className="user-form" onSubmit={handleSaveUser}>
                <label>
                  Nombre
                  <input name="nombre" value={userForm.nombre} onChange={handleUserChange} required />
                </label>
                <label>
                  Apellido
                  <input name="apellido" value={userForm.apellido} onChange={handleUserChange} />
                </label>
                <label>
                  Usuario
                  <input name="username" value={userForm.username} onChange={handleUserChange} required />
                </label>
                <label>
                  Correo
                  <input name="correo" type="email" value={userForm.correo} onChange={handleUserChange} />
                </label>
                <label>
                  Rol
                  <select name="id_rol" value={userForm.id_rol} onChange={handleUserChange} required>
                    <option value="">Seleccionar rol</option>
                    {roles.map((rol) => (
                      <option key={rol.id_rol} value={rol.id_rol}>
                        {rol.nombre_display}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Contraseña
                  <input
                    name="password"
                    type="password"
                    value={userForm.password}
                    onChange={handleUserChange}
                    required={!userForm.id_usuario}
                    placeholder={userForm.id_usuario ? 'Dejar vacio para mantener' : ''}
                  />
                </label>
                <label className="checkbox-label">
                  <input name="estado" type="checkbox" checked={userForm.estado} onChange={handleUserChange} />
                  Usuario activo
                </label>
                <button type="submit" disabled={savingUser}>
                  {savingUser ? 'Guardando...' : userForm.id_usuario ? 'Actualizar usuario' : 'Crear usuario'}
                </button>
              </form>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Usuario</th>
                      <th>Nombre</th>
                      <th>Rol</th>
                      <th>Estado</th>
                      <th>Accion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usuarios.map((item) => (
                      <tr key={item.id_usuario}>
                        <td>{item.username}</td>
                        <td>{item.nombre} {item.apellido}</td>
                        <td>{item.rol_nombre}</td>
                        <td>
                          <span className={item.estado ? 'badge active' : 'badge inactive'}>
                            {item.estado ? 'Activo' : 'Inactivo'}
                          </span>
                        </td>
                        <td>
                          <button type="button" className="small-button" onClick={() => handleEditUser(item)}>
                            Editar
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : activeModule === 'roles' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Propietario</span>
                  <h2>Gestionar roles y permisos</h2>
                  <p>Consulta fija de lo que puede hacer cada rol del sistema.</p>
                </div>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <div className="roles-layout">
                <div className="role-list">
                  {roles.map((rol) => (
                    <button
                      className={String(rol.id_rol) === String(selectedRoleId) ? 'role-button selected' : 'role-button'}
                      key={rol.id_rol}
                      type="button"
                      onClick={() => handleSelectRole(rol)}
                    >
                      <strong>{rol.nombre_display}</strong>
                      <span>{rol.permisos.length} permisos</span>
                    </button>
                  ))}
                </div>

                <section className="permission-panel">
                  <div className="permission-summary">
                    <span className="eyebrow">Rol seleccionado</span>
                    <h3>{selectedRole?.nombre_display || 'Sin seleccionar'}</h3>
                    <p>{selectedRole?.descripcion || 'Selecciona un rol para ver su matriz de permisos.'}</p>
                  </div>

                  <div className="permission-groups">
                    {Object.entries(permissionsByModule).map(([modulo, modulePermissions]) => (
                      <section className="permission-group" key={modulo}>
                        <h3>{modulo}</h3>
                        <div className="permission-list">
                          {modulePermissions.map((permiso) => {
                            const assigned = Boolean(selectedRole?.permisos.includes(permiso.id_permiso));
                            return (
                              <div className="permission-option readonly" key={permiso.id_permiso}>
                                <span className={assigned ? 'permission-dot yes' : 'permission-dot no'}>
                                  {assigned ? 'Sí' : 'No'}
                                </span>
                                <span>
                                  <strong>{permiso.nombre}</strong>
                                  <small>{permiso.descripcion}</small>
                                </span>
                              </div>
                            );
                          })}
                        </div>
                      </section>
                    ))}
                  </div>
                </section>
              </div>
            </section>
          ) : activeModule === 'entradas' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Ayudante de cocina</span>
                  <h2>Registrar entradas de insumos</h2>
                  <p>Registra los productos que ingresan al almacen y actualiza el stock.</p>
                </div>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <div className="purchase-summary">
                <article className="summary-card">
                  <span className="eyebrow">Compras registradas</span>
                  <strong>{entradas.length}</strong>
                  <small>Entradas de almacén</small>
                </article>
                <article className="summary-card">
                  <span className="eyebrow">Gasto total</span>
                  <strong>{formatMoney(totalCompras)}</strong>
                  <small>Monto acumulado por entradas</small>
                </article>
              </div>

              <div className="entry-layout">
                <section className="stock-form">
                  <div>
                    <span className="eyebrow">Insumos definidos</span>
                    <h3>Stock mínimo fijo</h3>
                  </div>
                  <div className="defined-supply-list">
                    {insumos.map((insumo) => (
                      <p className="stock-hint" key={insumo.id_insumo}>
                        {insumo.nombre}: mínimo {formatCantidad(insumo.stock_minimo)} {insumo.unidad_abreviatura || insumo.unidad}
                      </p>
                    ))}
                  </div>
                </section>

                <form className="stock-form" onSubmit={handleSaveEntrada}>
                  <div>
                    <span className="eyebrow">Entrada</span>
                    <h3>Ingresar cantidad</h3>
                  </div>
                  <label>
                    Insumo
                    <select name="id_insumo" value={entradaForm.id_insumo} onChange={handleEntradaChange} required>
                      <option value="">Seleccionar insumo</option>
                      {insumos.map((insumo) => (
                        <option key={insumo.id_insumo} value={insumo.id_insumo}>
                          {insumo.nombre} ({insumo.unidad})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Tipo de compra
                    <select name="tipo_compra" value={entradaForm.tipo_compra} onChange={handleEntradaChange} required>
                      {opcionesCompra.map((opcion) => (
                        <option key={opcion.value} value={opcion.value}>{opcion.label}</option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Cantidad comprada
                    <input
                      min="0.001"
                      name="cantidad_compra"
                      step="0.001"
                      type="number"
                      value={entradaForm.cantidad_compra}
                      onChange={handleEntradaChange}
                      required
                    />
                  </label>
                  <label>
                    Costo por {labelsCompra[entradaForm.tipo_compra]}
                    <input
                      min="0"
                      name="costo_compra"
                      step="0.01"
                      type="number"
                      value={entradaForm.costo_compra}
                      onChange={handleEntradaChange}
                    />
                  </label>
                  <label>
                    Observacion
                    <textarea name="observacion" value={entradaForm.observacion} onChange={handleEntradaChange} />
                  </label>
                  {selectedInsumo && (
                    <p className="stock-hint">
                      Stock actual: {formatCantidad(selectedInsumo.cantidad_actual)} {selectedInsumo.unidad_abreviatura || selectedInsumo.unidad}
                    </p>
                  )}
                  <div className="conversion-preview">
                    <span className="eyebrow">Conversión a stock</span>
                    <p className="stock-hint">
                      Se guardará: {formatCantidad(entradaConvertida.cantidadKg)} kg
                      <small>Costo por kg: {formatMoney(entradaConvertida.costoUnitarioKg)}</small>
                      <small>Total compra: {formatMoney(entradaConvertida.total)}</small>
                    </p>
                  </div>
                  <button type="submit" disabled={savingEntrada || !insumos.length}>
                    {savingEntrada ? 'Registrando...' : 'Registrar entrada'}
                  </button>
                </form>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Insumo</th>
                      <th>Categoria</th>
                      <th>Unidad</th>
                      <th>Stock actual</th>
                      <th>Minimo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {insumos.map((insumo) => (
                      <tr key={insumo.id_insumo}>
                        <td>{insumo.nombre}</td>
                        <td>{insumo.categoria}</td>
                        <td>{insumo.unidad}</td>
                        <td>{formatCantidad(insumo.cantidad_actual)}</td>
                        <td>{formatCantidad(insumo.stock_minimo)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Usuario</th>
                      <th>Detalle</th>
                      <th>Total compra</th>
                      <th>Observacion</th>
                    </tr>
                  </thead>
                  <tbody>
                    {entradas.slice(0, 8).map((entrada) => (
                      <tr key={entrada.id_entrada}>
                        <td>{new Date(entrada.fecha_entrada).toLocaleString()}</td>
                        <td>{entrada.usuario}</td>
                        <td>
                          {entrada.detalles.map((detalle) => (
                            <span className="detail-chip" key={detalle.id_detalle_entrada}>
                              {detalle.insumo}: {formatCantidad(detalle.cantidad)} {detalle.unidad}
                              {' - '}
                              {formatMoney(detalle.subtotal)}
                            </span>
                          ))}
                        </td>
                        <td>{formatMoney(entrada.total_compra)}</td>
                        <td>{entrada.observacion || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : activeModule === 'stock' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Stock</span>
                  <h2>Consultar stock disponible</h2>
                  <p>Revisa cantidades actuales y alertas por nivel minimo.</p>
                </div>
                <button type="button" className="secondary-button" onClick={loadStockModule}>
                  Actualizar
                </button>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              {canEditStockMinimo && stockMinimoForm.id_insumo && (
                <form className="stock-form" onSubmit={handleSaveStockMinimo}>
                  <div>
                    <span className="eyebrow">Configuracion</span>
                    <h3>Editar stock minimo</h3>
                  </div>
                  <label>
                    Insumo
                    <input type="text" value={stockMinimoForm.nombre} readOnly />
                  </label>
                  <label>
                    Nuevo minimo ({stockMinimoForm.unidad})
                    <input
                      min="0"
                      name="stock_minimo"
                      step="0.001"
                      type="number"
                      value={stockMinimoForm.stock_minimo}
                      onChange={handleStockMinimoChange}
                      required
                    />
                  </label>
                  <p className="stock-hint">
                    Este valor se guarda en el insumo y desde ahi se validan salidas, alertas y reportes BI.
                  </p>
                  <div className="form-actions">
                    <button type="submit" disabled={savingStockMinimo}>
                      {savingStockMinimo ? 'Guardando...' : 'Guardar minimo'}
                    </button>
                    <button type="button" className="secondary-button" onClick={handleCancelStockMinimoEdit}>
                      Cancelar
                    </button>
                  </div>
                </form>
              )}

              <div className="stock-summary">
                {insumos.map((insumo) => {
                  const isLow = isStockMinimo(insumo);
                  return (
                    <article className={isLow ? 'stock-card low' : 'stock-card'} key={insumo.id_insumo}>
                      <span className="eyebrow">{insumo.categoria}</span>
                      <h3>{insumo.nombre}</h3>
                      <strong>{formatCantidad(insumo.cantidad_actual)} {insumo.unidad_abreviatura || insumo.unidad}</strong>
                      <small>Minimo: {formatCantidad(insumo.stock_minimo)}</small>
                    </article>
                  );
                })}
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Insumo</th>
                      <th>Unidad</th>
                      <th>Stock actual</th>
                      <th>Stock minimo</th>
                      <th>Estado</th>
                      {canEditStockMinimo && <th>Accion</th>}
                    </tr>
                  </thead>
                  <tbody>
                    {insumos.map((insumo) => {
                      const isLow = isStockMinimo(insumo);
                      return (
                        <tr key={insumo.id_insumo}>
                          <td>{insumo.nombre}</td>
                          <td>{insumo.unidad}</td>
                          <td>{formatCantidad(insumo.cantidad_actual)}</td>
                          <td>{formatCantidad(insumo.stock_minimo)}</td>
                          <td>
                            <span className={isLow ? 'badge inactive' : 'badge active'}>
                              {isLow ? 'Stock minimo' : 'Stock normal'}
                            </span>
                          </td>
                          {canEditStockMinimo && (
                            <td>
                              <button type="button" className="small-button" onClick={() => handleEditStockMinimo(insumo)}>
                                Editar minimo
                              </button>
                            </td>
                          )}
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              <section className="notification-panel">
                <div>
                  <span className="eyebrow">Alertas</span>
                  <h3>Notificaciones de stock minimo</h3>
                </div>
                {notificaciones.length ? (
                  <div className="notification-list">
                    {notificaciones.slice(0, 6).map((notificacion) => (
                      <p className="stock-hint" key={notificacion.id_notificacion}>
                        {notificacion.mensaje}
                      </p>
                    ))}
                  </div>
                ) : (
                  <p>No hay alertas registradas.</p>
                )}
              </section>
            </section>
          ) : activeModule === 'disponibilidad' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">{usuario.rol_nombre}</span>
                  <h2>Revisar disponibilidad</h2>
                  <p>Verifica si los insumos principales estan listos para la produccion diaria.</p>
                </div>
                <button type="button" className="secondary-button" onClick={loadDisponibilidadModule}>
                  Actualizar
                </button>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}

              <div className="availability-grid">
                {disponibilidadProduccion.map(({ nombre, insumo, disponible, critico }) => (
                  <article className={disponible ? 'availability-card ready' : 'availability-card warning'} key={nombre}>
                    <span className="eyebrow">{insumo?.categoria || 'Pendiente'}</span>
                    <h3>{nombre}</h3>
                    {insumo ? (
                      <>
                        <strong>{formatCantidad(insumo.cantidad_actual)} {insumo.unidad_abreviatura || insumo.unidad}</strong>
                        <small>Minimo: {formatCantidad(insumo.stock_minimo)}</small>
                        <span className={critico ? 'badge inactive' : 'badge active'}>
                          {critico ? 'Stock minimo' : 'Stock normal'}
                        </span>
                      </>
                    ) : (
                      <>
                        <strong>Sin registro</strong>
                        <small>Maria debe registrar este insumo primero.</small>
                        <span className="badge inactive">No disponible</span>
                      </>
                    )}
                  </article>
                ))}
              </div>

              <section className="production-reference">
                <div>
                  <span className="eyebrow">Referencia de preparación</span>
                  <h3>Plato entero</h3>
                </div>
                <div className="reference-grid">
                  {recetaPlatoEntero.map((item) => (
                    <span className="detail-chip" key={item.nombre}>
                      {item.nombre}: {item.cantidad}
                    </span>
                  ))}
                </div>
                <div>
                  <span className="eyebrow">Medio plato</span>
                  <div className="reference-grid">
                    {recetaMedioPlato.map((item) => (
                      <span className="detail-chip" key={item.nombre}>
                        {item.nombre}: {item.cantidad}
                      </span>
                    ))}
                  </div>
                </div>
                <div>
                  <span className="eyebrow">Tipos de carne</span>
                  <div className="reference-grid">
                    {carnesPorPlato.map((item) => (
                      <span className="detail-chip" key={item}>{item}</span>
                    ))}
                  </div>
                </div>
              </section>
            </section>
          ) : activeModule === 'alertas' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Chef</span>
                  <h2>Alertas de insumos</h2>
                  <p>Consulta avisos de stock mínimo y feriados próximos para coordinar la preparación.</p>
                </div>
                <button type="button" className="secondary-button" onClick={loadAlertasModule}>
                  Actualizar
                </button>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}

              {notificaciones.length ? (
                <div className="alert-list">
                  {notificaciones.map((notificacion) => (
                    <article
                      className={
                        notificacion.tipo === 'stock_minimo' || notificacion.tipo === 'stock_preventivo'
                          ? 'alert-item alert-highlight'
                          : 'alert-item'
                      }
                      key={notificacion.id_notificacion}
                    >
                      <div>
                        <span className="eyebrow">
                          {textoAlerta(notificacion.insumo || notificacion.feriado || 'Planificación')}
                        </span>
                        <h3>{textoAlerta(notificacion.mensaje)}</h3>
                        <p>
                          {notificacion.fecha_feriado
                            ? `Feriado: ${notificacion.fecha_feriado}`
                            : new Date(notificacion.fecha).toLocaleString()}
                        </p>
                        <p>{labelsTipoNotificacion[notificacion.tipo] || textoAlerta(notificacion.tipo)}</p>
                      </div>
                      <span className={notificacion.estado === 'pendiente' ? 'badge inactive' : 'badge active'}>
                        {labelsEstadoNotificacion[notificacion.estado] || textoAlerta(notificacion.estado)}
                      </span>
                    </article>
                  ))}
                </div>
              ) : (
                <section className="notification-panel">
                  <span className="eyebrow">Sin alertas</span>
                  <p>No hay notificaciones de stock o feriados por ahora.</p>
                </section>
              )}
            </section>
          ) : activeModule === 'feriados' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Sincronización</span>
                  <h2>Calendario de planificación</h2>
                  <p>Sincroniza feriados y fechas de alta demanda para planificar compras y produccion.</p>
                </div>
                <button type="button" className="secondary-button" onClick={loadFeriadosModule} disabled={syncingFeriados}>
                  {syncingFeriados ? 'Sincronizando...' : 'Sincronizar'}
                </button>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Nombre</th>
                      <th>Pais</th>
                    </tr>
                  </thead>
                  <tbody>
                    {feriados.map((feriado) => (
                      <tr key={feriado.id_feriado}>
                        <td>{feriado.fecha}</td>
                        <td>{feriado.nombre}</td>
                        <td>{feriado.pais}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : activeModule === 'reportes' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <h2>Reportes</h2>
                </div>
                <button type="button" className="secondary-button" onClick={() => refreshBiModule('reportes')} disabled={runningEtl}>
                  {runningEtl ? 'Actualizando...' : 'Actualizar'}
                </button>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <div className="purchase-summary">
                <article className="summary-card">
                  <span className="eyebrow">Ventas</span>
                  <strong>{formatMoney(biData.resumen?.ventas_estimadas)}</strong>
                  <small>Total estimado por platos vendidos.</small>
                </article>
                <article className="summary-card">
                  <span className="eyebrow">Ganancia</span>
                  <strong>{formatMoney(biData.resumen?.ganancia_estimada)}</strong>
                  <small>Ventas menos costo de insumos usados.</small>
                </article>
                <article className="summary-card">
                  <span className="eyebrow">Vendido</span>
                  <strong>{formatCantidad(biData.resumen?.total_salidas)} kg</strong>
                  <small>Insumos usados en salidas.</small>
                </article>
                <article className="summary-card">
                  <span className="eyebrow">Compras</span>
                  <strong>{formatMoney(biData.resumen?.costo_compras)}</strong>
                  <small>Costo total de abastecimiento.</small>
                </article>
                <article className="summary-card">
                  <span className="eyebrow">Costo insumos usados</span>
                  <strong>{formatMoney(biData.resumen?.costo_consumido)}</strong>
                  <small>Costo de ingredientes usados en salidas.</small>
                </article>
                <article className="summary-card">
                  <span className="eyebrow">Merma</span>
                  <strong>{formatCantidad(biData.resumen?.total_mermas)} kg</strong>
                  <small>{formatMoney(biData.resumen?.costo_merma)} en perdida estimada.</small>
                </article>
              </div>

              <div className="monthly-report-grid">
                {mesesReporte.map((item) => (
                  <article className="monthly-report-card" key={item.key}>
                    <div className="monthly-card-head">
                      <span className="eyebrow">{item.nombre}</span>
                      <button type="button" className="secondary-button compact" onClick={() => downloadMonthlyReport(item)}>
                        Descargar PDF
                      </button>
                    </div>
                    <div className="monthly-metrics">
                      <span>
                        Ventas
                        <strong>{formatMoney(item.ventas)}</strong>
                      </span>
                      <span>
                        Ganancia
                        <strong>{formatMoney(item.utilidadNeta)}</strong>
                      </span>
                      <span>
                        Costo usado
                        <strong>{formatMoney(item.costoConsumido)}</strong>
                      </span>
                      <span>
                        Compras
                        <strong>{formatMoney(item.costoCompras)}</strong>
                      </span>
                      <span>
                        Platos
                        <strong>{formatCantidad(item.platos)}</strong>
                      </span>
                      <span>
                        Consumo
                        <strong>{formatCantidad(item.consumoKg)} kg</strong>
                      </span>
                      <span>
                        Merma
                        <strong>{formatMoney(item.costoMerma)}</strong>
                      </span>
                    </div>
                  </article>
                ))}
              </div>

              <div className="table-wrap">
                <table>
                  <caption>Resumen mensual</caption>
                  <thead>
                    <tr>
                      <th>Mes</th>
                      <th>Platos vendidos</th>
                      <th>Ventas</th>
                      <th>Costo usado</th>
                      <th>Compras</th>
                      <th>Merma</th>
                      <th>Perdida por merma</th>
                      <th>Ganancia final</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mesesReporte.map((item) => (
                      <tr key={item.key}>
                        <td>{item.nombre}</td>
                        <td>{formatCantidad(item.platos)}</td>
                        <td>{formatMoney(item.ventas)}</td>
                        <td>{formatMoney(item.costoConsumido)}</td>
                        <td>{formatMoney(item.costoCompras)}</td>
                        <td>{formatCantidad(item.mermaKg)} kg</td>
                        <td>{formatMoney(item.costoMerma)}</td>
                        <td>{formatMoney(item.utilidadNeta)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="report-filter">
                <label>
                  Buscar historial de ventas
                  <input
                    type="search"
                    value={historialVentaFiltro}
                    onChange={(event) => setHistorialVentaFiltro(event.target.value)}
                    placeholder="Fecha, mes, platos o monto"
                  />
                </label>
                <span>
                  {historialVentasFiltrado.length} dias encontrados
                </span>
              </div>

              <div className="table-wrap">
                <table>
                  <caption>Historial diario de ventas</caption>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Mes</th>
                      <th>Platos vendidos</th>
                      <th>Ventas</th>
                      <th>Costo usado</th>
                      <th>Ganancia</th>
                    </tr>
                  </thead>
                  <tbody>
                    {historialVentasFiltrado.map((item) => (
                      <tr key={item.fecha}>
                        <td>{formatDateOnly(item.fecha)}</td>
                        <td>{monthNameFromDate(item.fecha)}</td>
                        <td>{formatCantidad(item.platos)}</td>
                        <td>{formatMoney(item.ventas)}</td>
                        <td>{formatMoney(item.costo)}</td>
                        <td>{formatMoney(item.ganancia)}</td>
                      </tr>
                    ))}
                    {!historialVentasFiltrado.length && (
                      <tr>
                        <td colSpan="6">No hay ventas que coincidan con la busqueda.</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>

              <div className="table-wrap">
                <table>
                  <caption>Consumo por insumo</caption>
                  <thead>
                    <tr>
                      <th>Insumo</th>
                      <th>Consumo total</th>
                      <th>Movimientos</th>
                    </tr>
                  </thead>
                  <tbody>
                    {biData.consumo_por_insumo.map((item) => (
                      <tr key={item.id_dim_insumo__nombre}>
                        <td>{item.id_dim_insumo__nombre}</td>
                        <td>{formatCantidad(item.total)} kg</td>
                        <td>{item.movimientos}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="table-wrap">
                <table>
                  <caption>Merma registrada</caption>
                  <thead>
                    <tr>
                      <th>Insumo con merma</th>
                      <th>Cantidad kg</th>
                      <th>Costo estimado Bs</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(biData.merma_por_insumo?.length ? biData.merma_por_insumo : [{ id_dim_insumo__nombre: 'Sin registros de merma', cantidad: 0, costo: 0 }]).map((item) => (
                      <tr key={item.id_dim_insumo__nombre}>
                        <td>{item.id_dim_insumo__nombre}</td>
                        <td>{formatCantidad(item.cantidad)}</td>
                        <td>{formatMoney(item.costo)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>

              <div className="table-wrap">
                <table>
                  <caption>Compras por insumo</caption>
                  <thead>
                    <tr>
                      <th>Insumo</th>
                      <th>Ingresado</th>
                      <th>Costo compra</th>
                    </tr>
                  </thead>
                  <tbody>
                    {biData.entradas_por_insumo.map((item) => (
                      <tr key={item.id_dim_insumo__nombre}>
                        <td>{item.id_dim_insumo__nombre}</td>
                        <td>{formatCantidad(item.total)} kg</td>
                        <td>{formatMoney(item.costo)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : activeModule === 'dashboards' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <h2>Dashboards</h2>
                </div>
                <button type="button" className="secondary-button" onClick={() => refreshBiModule('dashboards')} disabled={runningEtl}>
                  {runningEtl ? 'Actualizando...' : 'Actualizar'}
                </button>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <div className="powerbi-kpi-grid">
                {decisionKpis.map((kpi, index) => (
                  <article className={`powerbi-kpi-card ${kpi?.estado || 'normal'}`} key={kpi?.codigo || index}>
                    <span>{index + 1}</span>
                    <div>
                      <small>{kpi?.nombre || 'Indicador'}</small>
                      <strong>{formatKpiValue(kpi)}</strong>
                    </div>
                    <em>{kpi?.decision || 'Sin decision sugerida.'}</em>
                  </article>
                ))}
              </div>

              <div className="powerbi-layout">
                <section className="powerbi-visual powerbi-wide">
                  <div>
                    <span className="eyebrow">Indicador 1</span>
                    <h3>Stock actual frente al minimo</h3>
                    <small>Compara disponibilidad real contra el punto minimo definido para compra.</small>
                  </div>
                  <div className="powerbi-split">
                    <BiChart option={stockRiskGaugeOption} height={300} />
                    <BiChart option={stockVsMinimoOption} height={300} />
                  </div>
                </section>

                <section className="powerbi-visual">
                  <div>
                    <span className="eyebrow">Indicador 2</span>
                    <h3>Platos disponibles por tipo</h3>
                    <small>Calcula capacidad de produccion segun recetas y stock disponible.</small>
                  </div>
                  <BiChart option={platosDisponiblesOption} height={310} />
                  <div className="decision-reading">
                    <strong>{formatCantidad(totalPlatosDisponibles)} platos posibles</strong>
                    <small>{platoLimitante ? `El insumo limitante principal es ${platoLimitante.insumo_limitante}.` : 'Sin referencia de platos.'}</small>
                  </div>
                </section>

                <section className="powerbi-visual">
                  <div>
                    <span className="eyebrow">Indicador 3</span>
                    <h3>Demanda promedio por dia y franja horaria</h3>
                    <small>Identifica los horarios que requieren mayor preparacion previa.</small>
                  </div>
                  <BiChart
                    height={310}
                    onEvents={{
                      click: (params) => setSelectedDemandIndex(params.dataIndex || 0),
                    }}
                    option={demandaFranjaOption}
                  />
                  <div className="decision-reading">
                    <strong>{demandaPico ? `${demandaPico.nombre_dia} ${demandaPico.franja_horaria}` : 'Sin demanda registrada'}</strong>
                    <small>{demandaPico ? `Barra seleccionada: ${formatCantidad(demandaPico.promedio_platos)} platos promedio de ${demandaPico.plato}.` : 'Registra salidas para calcular demanda.'}</small>
                    {demandaDetalleHorario.length ? (
                      <div className="demand-detail-list">
                        {demandaDetalleHorario.map((item) => (
                          <span key={`${item.nombre_dia}-${item.franja_horaria}-${item.plato}`}>
                            {item.plato}: {formatCantidad(item.promedio_platos)} platos
                          </span>
                        ))}
                      </div>
                    ) : null}
                  </div>
                </section>

                <section className="powerbi-visual powerbi-wide">
                  <div>
                    <span className="eyebrow">Indicador 4</span>
                    <h3>Variacion y tendencia de ventas/consumo</h3>
                    <small>Compara ventas estimadas contra consumo de insumos para decidir si ajustar compras y produccion.</small>
                  </div>
                  <BiChart option={tendenciaVentasOption} height={340} />
                  <div className="decision-reading">
                    <strong>{ultimaTendencia ? tendenciaTexto(ultimaTendencia.variacion_ventas, ultimaTendencia.estado_tendencia) : 'Sin tendencia suficiente'}</strong>
                    <small>Ultima lectura semanal para ajustar volumen de compra y produccion.</small>
                  </div>
                </section>

                <section className="powerbi-visual powerbi-wide">
                  <div>
                    <span className="eyebrow">Indicador 5</span>
                    <h3>Cobertura y riesgo de desabastecimiento</h3>
                    <small>Prioriza insumos segun los dias estimados que alcanza el stock actual.</small>
                  </div>
                  <div className="powerbi-split">
                    <BiChart option={coberturaOption} height={350} />
                    <div className="purchase-priority-table">
                      <div className="table-head">
                        <span>Insumo</span>
                        <span>Cobertura</span>
                        <span>Decision</span>
                      </div>
                    {coberturaCritica.map((item) => {
                      const dias = Number(item.cobertura_dias || 0);
                      const riesgo = dias <= 2 ? 'critico' : dias <= 5 ? 'preventivo' : 'normal';
                      return (
                          <div className={`table-row ${riesgo}`} key={item.insumo}>
                            <strong>{item.insumo}</strong>
                            <span>{dias.toFixed(1)} dias</span>
                            <em>{item.recomendacion_compra || (riesgo === 'critico' ? 'Compra prioritaria' : riesgo === 'preventivo' ? 'Revisar compra' : 'Compra normal')}</em>
                          </div>
                      );
                    })}
                    </div>
                  </div>
                </section>

                <section className="powerbi-visual">
                  <div>
                    <span className="eyebrow">Indicador 6</span>
                    <h3>Merma por insumo</h3>
                    <small>Controla perdidas por deterioro, manipulacion o ajustes manuales.</small>
                  </div>
                  <BiChart option={mermaOption} height={310} />
                  <div className="decision-reading">
                    <strong>{formatCantidad(totalMermaKg)} kg | {formatMoney(totalMermaCosto)}</strong>
                    <small>{kpiMerma?.decision || 'Sin mermas registradas en el periodo.'}</small>
                  </div>
                </section>

                <section className="powerbi-visual">
                  <div>
                    <span className="eyebrow">Indicador 7</span>
                    <h3>Cumplimiento de meta de ventas</h3>
                    <small>Compara las ventas del ultimo mes registrado contra la meta mensual estimada.</small>
                  </div>
                  <BiChart option={metaVentasOption} height={310} />
                  <div className="decision-reading">
                    <strong>{kpiMeta?.lectura || 'Sin meta calculada.'}</strong>
                    <small>{kpiMeta?.decision || 'Registrar ventas para comparar cumplimiento.'}</small>
                  </div>
                </section>

                <section className="powerbi-visual powerbi-wide">
                  <div>
                    <span className="eyebrow">Analisis complementario</span>
                    <h3>Costos de abastecimiento y entradas</h3>
                    <small>Relaciona compras mensuales con cantidad abastecida para explicar variaciones de costo.</small>
                  </div>
                  <BiChart option={costosOption} height={330} />
                </section>

                <section className="powerbi-visual">
                  <div>
                    <span className="eyebrow">Analisis complementario</span>
                    <h3>Producto mas consumido</h3>
                  </div>
                  <div className="bar-list">
                    {biData.consumo_por_insumo.map((item) => (
                      <div className="bar-row" key={item.id_dim_insumo__nombre}>
                        <span>{item.id_dim_insumo__nombre}</span>
                        <div className="bar-track">
                          <div className="bar-fill salida" style={{ width: `${Math.max((Number(item.total || 0) / maxConsumo) * 100, 4)}%` }} />
                        </div>
                        <strong>{formatCantidad(item.total)} kg</strong>
                      </div>
                    ))}
                  </div>
                </section>

                <section className="powerbi-visual">
                  <div>
                    <span className="eyebrow">Analisis complementario</span>
                    <h3>Estimacion del proximo mes</h3>
                    <small>Calcula una referencia futura usando el promedio de los ultimos meses disponibles.</small>
                  </div>
                  <div className="projection-grid">
                    <span>
                      Ventas estimadas
                      <strong>{formatMoney(analisisComplementarios.proyeccion_proximo_mes?.ventas_estimadas)}</strong>
                    </span>
                    <span>
                      Ganancia estimada
                      <strong>{formatMoney(analisisComplementarios.proyeccion_proximo_mes?.ganancia_estimada)}</strong>
                    </span>
                    <small>{analisisComplementarios.proyeccion_proximo_mes?.metodo || 'Sin datos historicos.'}</small>
                  </div>
                  <div className="analysis-reading">
                    <strong>{analisisComplementarios.proyeccion_proximo_mes?.lectura || 'Sin lectura de proyeccion.'}</strong>
                    <small>{analisisComplementarios.proyeccion_proximo_mes?.decision || 'Registrar mas ventas para generar una decision.'}</small>
                  </div>
                </section>
              </div>
            </section>
          ) : activeModule === 'mermas' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Stock</span>
                  <h2>Registrar merma</h2>
                  <p>Registra perdidas reales de insumos.</p>
                </div>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <div className="entry-layout">
                <form className="stock-form" onSubmit={handleSaveMerma}>
                  <div>
                    <span className="eyebrow">Merma manual</span>
                    <h3>Perdida de insumo</h3>
                  </div>
                  <label>
                    Insumo
                    <select name="id_insumo" value={mermaForm.id_insumo} onChange={handleMermaChange} required>
                      <option value="">Seleccionar insumo</option>
                      {insumos.map((insumo) => (
                        <option key={insumo.id_insumo} value={insumo.id_insumo}>
                          {insumo.nombre} - stock {formatCantidad(insumo.cantidad_actual)} {insumo.unidad_abreviatura || insumo.unidad}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Cantidad perdida kg
                    <input
                      min="0.001"
                      name="cantidad"
                      step="0.001"
                      type="number"
                      value={mermaForm.cantidad}
                      onChange={handleMermaChange}
                      required
                    />
                  </label>
                  <input type="hidden" name="motivo" value="Recorte" />
                  <label>
                    Observacion
                    <textarea name="observacion" value={mermaForm.observacion} onChange={handleMermaChange} />
                  </label>
                  <button type="submit" disabled={savingMerma}>
                    {savingMerma ? 'Registrando...' : 'Registrar merma'}
                  </button>
                </form>

                <section className="notification-panel">
                  <div>
                    <span className="eyebrow">Efecto</span>
                    <h3>Descuento de stock</h3>
                    <p>El recorte resta inventario, no aumenta ventas ni platos preparados.</p>
                  </div>
                </section>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Insumo</th>
                      <th>Cantidad kg</th>
                      <th>Motivo</th>
                      <th>Usuario</th>
                    </tr>
                  </thead>
                  <tbody>
                    {mermas.slice(0, 12).map((merma) => (
                      <tr key={merma.id_merma}>
                        <td>{formatDateTime(merma.fecha_merma)}</td>
                        <td>{merma.insumo}</td>
                        <td>{formatCantidad(merma.cantidad)} {merma.unidad}</td>
                        <td>{merma.motivo}</td>
                        <td>{merma.usuario}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : activeModule === 'salidas' ? (
            <section className="management-panel">
              <div className="panel-heading">
                <div>
                  <span className="eyebrow">Ayudante de cocina</span>
                  <h2>Registrar salidas de insumos</h2>
                  <p>Descuenta los insumos utilizados durante la preparación.</p>
                </div>
              </div>

              {moduleError && <p className="error">{moduleError}</p>}
              {moduleMessage && <p className="success">{moduleMessage}</p>}

              <div className="entry-layout">
                <form className="stock-form" onSubmit={handleSaveSalida}>
                  <div>
                    <span className="eyebrow">Salida</span>
                    <h3>Registrar por plato</h3>
                  </div>
                  <label>
                    Tipo de pique
                    <select name="plato" value={salidaForm.plato} onChange={handleSalidaChange} required>
                      {Object.keys(recetasPorPlato).map((plato) => (
                        <option key={plato} value={plato}>
                          {plato}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Tamano
                    <select name="tamano" value={salidaForm.tamano} onChange={handleSalidaChange} required>
                      <option value="entero">Entero - 2.600 kg</option>
                      <option value="medio">Medio - 1.300 kg</option>
                    </select>
                  </label>
                  <label>
                    Cantidad de platos
                    <input
                      min="1"
                      name="cantidad_platos"
                      step="1"
                      type="number"
                      value={salidaForm.cantidad_platos}
                      onChange={handleSalidaChange}
                      required
                    />
                  </label>
                  <label>
                    Observacion
                    <textarea name="observacion" value={salidaForm.observacion} onChange={handleSalidaChange} />
                  </label>
                  <div className="recipe-preview">
                    <span className="eyebrow">Se descontara</span>
                    {salidaPorPlato.map((item) => (
                      <p className={item.insumo && item.cantidad <= item.disponible ? 'stock-hint' : 'stock-hint danger'} key={item.nombre}>
                        {item.nombre}: {formatCantidad(item.cantidad)} kg
                        {' '}
                        <small>
                          Disponible: {item.insumo ? `${formatCantidad(item.disponible)} ${item.insumo.unidad_abreviatura || item.insumo.unidad}` : 'sin registro'}
                        </small>
                      </p>
                    ))}
                    <p className="stock-hint">
                      Venta estimada: {formatMoney(precioSalida.totalVenta)}
                      <small>Precio unitario: {formatMoney(precioSalida.precioUnitario)}</small>
                    </p>
                  </div>
                  <button type="submit" disabled={savingSalida || !insumos.length}>
                    {savingSalida ? 'Registrando...' : 'Registrar salida'}
                  </button>
                </form>

                <section className="notification-panel">
                  <div>
                    <span className="eyebrow">Alertas recientes</span>
                    <h3>Stock minimo</h3>
                  </div>
                  {notificaciones.length ? (
                    <div className="notification-list">
                      {notificaciones.slice(0, 5).map((notificacion) => (
                        <p className="stock-hint" key={notificacion.id_notificacion}>
                          {notificacion.mensaje}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p>Las alertas apareceran despues de registrar salidas que alcancen el minimo.</p>
                  )}
                </section>
              </div>

              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Fecha</th>
                      <th>Usuario</th>
                      <th>Detalle</th>
                      <th>Motivo</th>
                    </tr>
                  </thead>
                  <tbody>
                    {salidas.slice(0, 8).map((salida) => (
                      <tr key={salida.id_salida}>
                        <td>{new Date(salida.fecha_salida).toLocaleString()}</td>
                        <td>{salida.usuario}</td>
                        <td>
                          {salida.detalles.map((detalle) => (
                            <span className="detail-chip" key={detalle.id_detalle_salida}>
                              {detalle.insumo}: {formatCantidad(detalle.cantidad)} {detalle.unidad}
                            </span>
                          ))}
                        </td>
                        <td>{salida.motivo || '-'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}
        </section>
      </main>
    );
  }

  return (
    <main className="page login-page">
      <section className="login-showcase" aria-hidden="true">
        <div className="login-showcase-card">
          <h2>Chillamicito</h2>
          <p>° Tradición de mi llajta °</p>
        </div>
      </section>
      <section className="login-panel">
        <div className="brand">
          <span className="login-emblem" aria-hidden="true">CH</span>
          <span className="eyebrow">Chillamicito</span>
          <h1>Inicio de sesión</h1>
          <p>Ingreso al sistema de gestión.</p>
        </div>

        <form onSubmit={handleSubmit}>
          <label>
            Usuario
            <input
              name="username"
              value={form.username}
              onChange={handleChange}
              autoComplete="username"
              required
            />
          </label>

          <label>
            Contraseña
            <input
              name="password"
              type="password"
              value={form.password}
              onChange={handleChange}
              autoComplete="current-password"
              required
            />
          </label>

          {error && <p className="error">{error}</p>}

          <button type="submit" disabled={loading}>
            {loading ? 'Ingresando...' : 'Iniciar sesión'}
          </button>
        </form>
      </section>
    </main>
  );
}

export default App;
