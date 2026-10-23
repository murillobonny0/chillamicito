from django.contrib.auth import authenticate
from decimal import Decimal
from datetime import datetime, timedelta

from django.db.models import Count, Q, Sum
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .etl import ejecutar_etl_movimientos_stock
from .movimientos import MovimientoCreateMixin
from .feriados_api import obtener_feriados_api
from .alertas import evaluar_todos_los_stocks, generar_alertas_feriados_proximos
from .models import (
    Categoria,
    DetalleEntrada,
    DetalleSalida,
    Entrada,
    Feriado,
    HechoMovimientoStock,
    Insumo,
    Merma,
    Notificacion,
    Permiso,
    RegistroETL,
    Rol,
    Salida,
    UnidadMedida,
    Usuario,
)

RECETAS_PLATOS = {
    'Chillami': {
        'Papa': Decimal('1'),
        'Carne': Decimal('1'),
        'Chorizo normal': Decimal('0.3'),
        'Tomate': Decimal('0.15'),
        'Cebolla': Decimal('0.15'),
        'Locoto': Decimal('0.1'),
    },
    'Macho': {
        'Papa': Decimal('1'),
        'Carne': Decimal('1'),
        'Chorizo normal': Decimal('0.3'),
        'Tomate': Decimal('0.15'),
        'Cebolla': Decimal('0.15'),
        'Locoto': Decimal('0.1'),
    },
    'Borracho': {
        'Papa': Decimal('1'),
        'Carne': Decimal('1'),
        'Chorizo normal': Decimal('0.3'),
        'Tomate': Decimal('0.15'),
        'Cebolla': Decimal('0.15'),
        'Locoto': Decimal('0.1'),
    },
    'Brasa': {
        'Papa': Decimal('1'),
        'Carne': Decimal('1'),
        'Chorizo parrillero': Decimal('0.3'),
        'Tomate': Decimal('0.15'),
        'Cebolla': Decimal('0.15'),
        'Locoto': Decimal('0.1'),
    },
    'Surubi': {
        'Papa': Decimal('1'),
        'Surubi': Decimal('1'),
        'Tomate': Decimal('0.15'),
        'Cebolla': Decimal('0.15'),
        'Locoto': Decimal('0.1'),
    },
}

NOMBRES_DIA = {
    1: 'Lunes',
    2: 'Martes',
    3: 'Miercoles',
    4: 'Jueves',
    5: 'Viernes',
    6: 'Sabado',
    7: 'Domingo',
}
META_VENTAS_FACTOR = Decimal('1.10')
from .serializers import (
    CategoriaSerializer,
    EntradaSerializer,
    FeriadoSerializer,
    InsumoSerializer,
    LoginSerializer,
    MermaSerializer,
    NotificacionSerializer,
    PermisoSerializer,
    RolSerializer,
    SalidaSerializer,
    UnidadMedidaSerializer,
    UsuarioGestionSerializer,
    UsuarioSerializer,
)


class EsPropietario(IsAuthenticated):
    """Permite acceso solo a usuarios autenticados con rol Propietario."""

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.rol == Rol.Nombre.PROPIETARIO


class EsOperacionStock(IsAuthenticated):
    """Permite operaciones de stock al ayudante de cocina."""

    roles_permitidos = {Rol.Nombre.AYUDANTE_COCINA}

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.rol in self.roles_permitidos


class EsGestionInsumo(IsAuthenticated):
    """Permite cambiar datos del insumo al propietario o al personal operativo."""

    roles_permitidos = {Rol.Nombre.PROPIETARIO, Rol.Nombre.AYUDANTE_COCINA, Rol.Nombre.CHEF}

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.rol in self.roles_permitidos


class EsConsultaStock(IsAuthenticated):
    """Permite consultar stock, alertas y feriados a roles operativos."""

    roles_permitidos = {Rol.Nombre.PROPIETARIO, Rol.Nombre.AYUDANTE_COCINA, Rol.Nombre.CHEF}

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.rol in self.roles_permitidos


class EsConsultaMerma(IsAuthenticated):
    """Permite revisar mermas a roles que trabajan con el control operativo."""

    roles_permitidos = {Rol.Nombre.PROPIETARIO, Rol.Nombre.AYUDANTE_COCINA}

    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.rol in self.roles_permitidos


class LoginView(APIView):
    """Valida credenciales con Django Auth y entrega un token para Axios."""

    authentication_classes = []
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        usuario = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )

        if not usuario or not usuario.estado:
            return Response(
                {'detail': 'Usuario o contrasena incorrectos.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        token, _ = Token.objects.get_or_create(user=usuario)

        return Response(
            {
                'token': token.key,
                'usuario': UsuarioSerializer(usuario).data,
            }
        )


class PerfilView(APIView):
    """Devuelve el usuario autenticado a partir del token enviado por Axios."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({'usuario': UsuarioSerializer(request.user).data})


class RolListView(ListAPIView):
    """Lista roles con sus permisos para el modulo de administracion."""

    permission_classes = [EsPropietario]
    queryset = Rol.objects.prefetch_related('rol_permisos__id_permiso').order_by('id_rol')
    serializer_class = RolSerializer


class PermisoListView(ListAPIView):
    """Lista todos los permisos disponibles del sistema."""

    permission_classes = [EsPropietario]
    queryset = Permiso.objects.all().order_by('modulo', 'id_permiso')
    serializer_class = PermisoSerializer


class UsuarioGestionListCreateView(ListCreateAPIView):
    """Permite al propietario listar y crear usuarios."""

    permission_classes = [EsPropietario]
    serializer_class = UsuarioGestionSerializer

    def get_queryset(self):
        """Trae usuarios con su rol para evitar consultas repetidas."""
        return Usuario.objects.select_related('id_rol').order_by('id_usuario')


class UsuarioGestionDetailView(RetrieveUpdateAPIView):
    """Permite consultar o actualizar un usuario especifico."""

    permission_classes = [EsPropietario]
    serializer_class = UsuarioGestionSerializer
    lookup_field = 'id_usuario'

    def get_queryset(self):
        """Incluye el rol del usuario al recuperar sus datos."""
        return Usuario.objects.select_related('id_rol')


class CatalogoStockView(APIView):
    """Devuelve catalogos base necesarios para formularios de stock."""

    permission_classes = [EsConsultaStock]

    def get(self, request):
        """Entrega categorias y unidades de medida en una sola respuesta."""
        return Response(
            {
                'categorias': CategoriaSerializer(Categoria.objects.order_by('nombre_categoria'), many=True).data,
                'unidades': UnidadMedidaSerializer(UnidadMedida.objects.order_by('nombre_unidad'), many=True).data,
            }
        )


class InsumoListCreateView(ListCreateAPIView):
    """Lista insumos activos y permite crear nuevos insumos segun permisos."""

    serializer_class = InsumoSerializer

    def get_permissions(self):
        """Usa permiso de consulta para GET y permiso operativo para creacion."""
        permission_class = EsConsultaStock if self.request.method == 'GET' else EsOperacionStock
        return [permission_class()]

    def get_queryset(self):
        """Carga insumo con categoria, unidad y stock actual."""
        return (
            Insumo.objects.select_related('id_categoria', 'id_unidad', 'stock')
            .filter(estado=True)
            .order_by('nombre')
        )


class InsumoDetailView(RetrieveUpdateAPIView):
    """Permite consultar o actualizar un insumo especifico, incluido su stock minimo."""

    serializer_class = InsumoSerializer
    lookup_field = 'id_insumo'

    def get_permissions(self):
        """Consulta para roles de stock; cambios solo para propietario o ayudante."""
        permission_class = EsConsultaStock if self.request.method == 'GET' else EsGestionInsumo
        return [permission_class()]

    def get_queryset(self):
        """Trae el insumo con sus relaciones para devolver categoria, unidad y stock actual."""
        return Insumo.objects.select_related('id_categoria', 'id_unidad', 'stock').filter(estado=True)


class EntradaListCreateView(MovimientoCreateMixin, ListCreateAPIView):
    """Lista y registra entradas de insumos al almacen."""

    permission_classes = [EsOperacionStock]
    serializer_class = EntradaSerializer

    def get_queryset(self):
        """Devuelve entradas recientes con sus detalles de insumos."""
        return (
            Entrada.objects.select_related('id_usuario')
            .prefetch_related('detalles__id_insumo__id_unidad')
            .order_by('-fecha_entrada', '-id_entrada')
        )


class SalidaListCreateView(MovimientoCreateMixin, ListCreateAPIView):
    """Lista y registra salidas de insumos por consumo de platos."""

    permission_classes = [EsOperacionStock]
    serializer_class = SalidaSerializer

    def get_queryset(self):
        """Devuelve salidas recientes con sus detalles de insumos."""
        return (
            Salida.objects.select_related('id_usuario')
            .prefetch_related('detalles__id_insumo__id_unidad')
            .order_by('-fecha_salida', '-id_salida')
        )


class MermaListCreateView(MovimientoCreateMixin, ListCreateAPIView):
    """Lista y registra mermas manuales de insumos."""

    serializer_class = MermaSerializer

    def get_permissions(self):
        """El chef consulta stock y alertas, pero no gestiona mermas."""
        permission_class = EsConsultaMerma if self.request.method == 'GET' else EsOperacionStock
        return [permission_class()]

    def get_queryset(self):
        """Devuelve mermas recientes con usuario, insumo y unidad."""
        return (
            Merma.objects.select_related('id_usuario', 'id_insumo__id_unidad')
            .order_by('-fecha_merma', '-id_merma')
        )


class NotificacionListView(ListAPIView):
    """Lista alertas internas de stock minimo y planificacion por feriados."""

    permission_classes = [EsConsultaStock]
    serializer_class = NotificacionSerializer

    def get_queryset(self):
        """Carga relaciones opcionales de insumo o feriado para mostrar alertas completas."""
        evaluar_todos_los_stocks()
        generar_alertas_feriados_proximos()
        return (
            Notificacion.objects.select_related('id_insumo__id_unidad', 'id_insumo__stock', 'id_feriado')
            .filter(estado=Notificacion.Estado.PENDIENTE)
            .order_by('-fecha', '-id_notificacion')
        )


class FeriadoListSyncView(APIView):
    """Consulta y sincroniza feriados desde Nager.Date y calendario local."""

    permission_classes = [EsConsultaStock]

    def get(self, request):
        """Devuelve feriados ya almacenados por anio y pais."""
        anio = int(request.query_params.get('anio', timezone.localdate().year))
        pais = request.query_params.get('pais', 'BO').upper()
        feriados = Feriado.objects.filter(fecha__year=anio, pais=pais).order_by('fecha')
        return Response(FeriadoSerializer(feriados, many=True).data)

    def post(self, request):
        """Sincroniza la API externa, guarda fechas y genera alertas preventivas."""
        anio = int(request.data.get('anio') or request.query_params.get('anio') or timezone.localdate().year)
        pais = (request.data.get('pais') or request.query_params.get('pais') or 'BO').upper()
        feriados_api = obtener_feriados_api(anio=anio, pais=pais)

        for item in feriados_api:
            Feriado.objects.update_or_create(
                fecha=item['fecha'],
                pais=item['pais'],
                defaults={'nombre': item['nombre']},
            )

        feriados = Feriado.objects.filter(fecha__year=anio, pais=pais).order_by('fecha')
        alertas_generadas = generar_alertas_feriados_proximos(feriados)
        return Response(
            {
                'mensaje': f'Feriados {pais} {anio} sincronizados correctamente.',
                'total': feriados.count(),
                'alertas_generadas': alertas_generadas,
                'feriados': FeriadoSerializer(feriados, many=True).data,
            }
        )

class EjecutarETLView(APIView):
    """Ejecuta la carga del Data Mart para reportes y Power BI."""

    permission_classes = [EsPropietario]

    def post(self, request):
        """Lanza el proceso ETL y devuelve el resultado de la ejecucion."""
        resultado = ejecutar_etl_movimientos_stock()
        return Response(resultado)


class BIDashboardView(APIView):
    """Entrega indicadores consolidados para reportes y dashboards."""

    permission_classes = [EsPropietario]

    def get(self, request):
        """Agrupa movimientos de stock en metricas de consumo, costo y rotacion."""
        if _data_mart_desactualizado():
            ejecutar_etl_movimientos_stock()

        hechos = HechoMovimientoStock.objects.select_related(
            'id_dim_insumo',
            'id_dim_categoria',
            'id_dim_tiempo',
            'id_dim_tipo_movimiento',
        )
        hechos = _filtrar_hechos_dashboard(hechos, request.query_params)
        salidas_filtradas = _filtrar_salidas_dashboard(Salida.objects.all(), request.query_params)
        ultimo_etl = RegistroETL.objects.order_by('-fecha_ejecucion').first()

        resumen = hechos.aggregate(
            movimientos=Count('id_hecho_movimiento_stock'),
            total_entradas=Sum('cantidad', filter=Q(id_dim_tipo_movimiento__nombre='Entrada')),
            total_salidas=Sum('cantidad', filter=Q(id_dim_tipo_movimiento__nombre='Salida')),
            total_mermas=Sum('cantidad', filter=Q(id_dim_tipo_movimiento__nombre='Merma')),
            costo_compras=Sum('costo_total', filter=Q(id_dim_tipo_movimiento__nombre='Entrada')),
            costo_consumido=Sum('costo_total', filter=Q(id_dim_tipo_movimiento__nombre='Salida')),
            costo_merma=Sum('costo_total', filter=Q(id_dim_tipo_movimiento__nombre='Merma')),
        )
        for clave in [
            'total_entradas',
            'total_salidas',
            'total_mermas',
            'costo_compras',
            'costo_consumido',
            'costo_merma',
        ]:
            resumen[clave] = resumen[clave] or Decimal('0')
        ventas_resumen = salidas_filtradas.aggregate(ventas=Sum('total_venta_estimado'))
        resumen['ventas_estimadas'] = ventas_resumen['ventas'] or Decimal('0')
        resumen['ganancia_estimada'] = resumen['ventas_estimadas'] - (resumen['costo_consumido'] or Decimal('0'))
        resumen['valor_invertido_stock'] = _valor_invertido_stock()

        consumo_por_insumo = list(
            hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
            .values('id_dim_insumo__nombre', 'id_dim_insumo__unidad_medida')
            .annotate(total=Sum('cantidad'), movimientos=Count('id_hecho_movimiento_stock'))
            .order_by('-total')[:8]
        )
        entradas_por_insumo = list(
            hechos.filter(id_dim_tipo_movimiento__nombre='Entrada')
            .values('id_dim_insumo__nombre', 'id_dim_insumo__unidad_medida')
            .annotate(total=Sum('cantidad'), costo=Sum('costo_total'))
            .order_by('-costo')[:8]
        )
        movimiento_por_categoria = list(
            hechos.values('id_dim_categoria__nombre_categoria', 'id_dim_tipo_movimiento__nombre')
            .annotate(total=Sum('cantidad'))
            .order_by('id_dim_categoria__nombre_categoria', 'id_dim_tipo_movimiento__nombre')
        )
        tendencia = list(
            hechos.values(
                'id_dim_tiempo__fecha',
                'id_dim_tiempo__nombre_mes',
                'id_dim_tiempo__nivel_demanda',
                'id_dim_tipo_movimiento__nombre',
            )
            .annotate(total=Sum('cantidad'), costo=Sum('costo_total'))
            .order_by('id_dim_tiempo__fecha', 'id_dim_tipo_movimiento__nombre')
        )
        consumo_mensual = list(
            hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
            .values(
                'id_dim_tiempo__anio',
                'id_dim_tiempo__mes',
                'id_dim_tiempo__nombre_mes',
                'id_dim_tiempo__nivel_demanda',
                'id_dim_tiempo__motivo_demanda',
            )
            .annotate(total=Sum('cantidad'), costo=Sum('costo_total'))
            .order_by('id_dim_tiempo__anio', 'id_dim_tiempo__mes')
        )
        compras_mensual = list(
            hechos.filter(id_dim_tipo_movimiento__nombre='Entrada')
            .values(
                'id_dim_tiempo__anio',
                'id_dim_tiempo__mes',
                'id_dim_tiempo__nombre_mes',
                'id_dim_tiempo__nivel_demanda',
                'id_dim_tiempo__motivo_demanda',
            )
            .annotate(
                total=Sum('cantidad'),
                costo=Sum('costo_total'),
                movimientos=Count('id_hecho_movimiento_stock'),
            )
            .order_by('id_dim_tiempo__anio', 'id_dim_tiempo__mes')
        )
        merma_mensual = list(
            hechos.filter(id_dim_tipo_movimiento__nombre='Merma')
            .values(
                'id_dim_tiempo__anio',
                'id_dim_tiempo__mes',
                'id_dim_tiempo__nombre_mes',
            )
            .annotate(total=Sum('cantidad'), costo=Sum('costo_total'), movimientos=Count('id_hecho_movimiento_stock'))
            .order_by('id_dim_tiempo__anio', 'id_dim_tiempo__mes')
        )
        merma_mensual_por_insumo = list(
            hechos.filter(id_dim_tipo_movimiento__nombre='Merma')
            .values(
                'id_dim_tiempo__anio',
                'id_dim_tiempo__mes',
                'id_dim_tiempo__nombre_mes',
                'id_dim_insumo__nombre',
                'id_dim_insumo__unidad_medida',
            )
            .annotate(cantidad=Sum('cantidad'), costo=Sum('costo_total'))
            .order_by('id_dim_tiempo__anio', 'id_dim_tiempo__mes', '-cantidad')
        )
        gastos_por_insumo = list(
            hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
            .values('id_dim_insumo__nombre')
            .annotate(costo=Sum('costo_total'), cantidad=Sum('cantidad'))
            .order_by('-costo')[:8]
        )
        rotacion_por_insumo = _rotacion_por_insumo(hechos)
        alertas_compra = _alertas_compra_actuales(hechos)
        meses_clave = [
            {'mes': 4, 'nombre': 'Abril', 'nivel': 'bajo', 'motivo': 'Mes de menor movimiento esperado.'},
            {'mes': 5, 'nombre': 'Mayo', 'nivel': 'bajo', 'motivo': 'Mes de menor movimiento esperado.'},
            {'mes': 6, 'nombre': 'Junio', 'nivel': 'bajo', 'motivo': 'Mes de menor movimiento esperado.'},
            {'mes': 8, 'nombre': 'Agosto', 'nivel': 'alto', 'motivo': 'Fiestas patrias y mayor actividad social.'},
            {'mes': 9, 'nombre': 'Septiembre', 'nivel': 'alto', 'motivo': 'Aniversario de Cochabamba y eventos sociales.'},
            {'mes': 11, 'nombre': 'Noviembre', 'nivel': 'alto', 'motivo': 'Promociones y eventos previos a fin de anio.'},
            {'mes': 12, 'nombre': 'Diciembre', 'nivel': 'alto', 'motivo': 'Graduaciones, fin de anio y reuniones.'},
        ]
        stock_actual = list(
            Insumo.objects.select_related('id_categoria', 'id_unidad', 'stock')
            .filter(estado=True)
            .values(
                'nombre',
                'id_categoria__nombre_categoria',
                'id_unidad__nombre_unidad',
                'stock__cantidad_actual',
                'stock_minimo',
            )
            .order_by('nombre')
        )
        demanda_por_dia_franja = _demanda_por_dia_franja(salidas_filtradas)
        platos_disponibles = _platos_disponibles()
        cobertura_estimada_stock = _cobertura_estimada_stock(hechos)
        tendencia_consumo_semanal = _tendencia_consumo_semanal(hechos)
        merma_por_insumo = _merma_por_insumo(hechos)
        ganancias_diarias = _ganancias_diarias(hechos, salidas_filtradas)
        granularidad_tendencia = _granularidad_tendencia(request.query_params)
        ganancias_semanales = _ganancias_semanales(
            hechos,
            salidas_filtradas,
            granularidad=granularidad_tendencia,
        )
        ganancias_mensuales = _ganancias_mensuales(hechos, salidas_filtradas)
        tendencia_ventas_consumo = _tendencia_ventas_consumo(
            hechos,
            ganancias_semanales,
            granularidad=granularidad_tendencia,
            salidas_base=salidas_filtradas,
        )
        kpis_decision = _kpis_decision(
            resumen=resumen,
            stock_actual=stock_actual,
            platos_disponibles=platos_disponibles,
            demanda_por_dia_franja=demanda_por_dia_franja,
            tendencia_consumo_semanal=tendencia_ventas_consumo,
            cobertura_estimada_stock=cobertura_estimada_stock,
            merma_por_insumo=merma_por_insumo,
            ganancias_mensuales=ganancias_mensuales,
        )
        analisis_complementarios = _analisis_complementarios(
            consumo_por_insumo=consumo_por_insumo,
            tendencia=tendencia,
            demanda_por_dia_franja=demanda_por_dia_franja,
            ganancias_mensuales=ganancias_mensuales,
            compras_mensual=compras_mensual,
        )

        return Response(
            {
                'ultimo_etl': {
                    'fecha': ultimo_etl.fecha_ejecucion if ultimo_etl else None,
                    'estado': ultimo_etl.estado if ultimo_etl else 'pendiente',
                    'descripcion': ultimo_etl.descripcion if ultimo_etl else 'Data Mart pendiente de carga.',
                },
                'resumen': resumen,
                'consumo_por_insumo': consumo_por_insumo,
                'entradas_por_insumo': entradas_por_insumo,
                'movimiento_por_categoria': movimiento_por_categoria,
                'tendencia': tendencia,
                'stock_actual': stock_actual,
                'consumo_mensual': consumo_mensual,
                'compras_mensual': compras_mensual,
                'merma_mensual': merma_mensual,
                'merma_mensual_por_insumo': merma_mensual_por_insumo,
                'gastos_por_insumo': gastos_por_insumo,
                'rotacion_por_insumo': rotacion_por_insumo,
                'alertas_compra': alertas_compra,
                'meses_clave': meses_clave,
                'demanda_por_dia_franja': demanda_por_dia_franja,
                'platos_disponibles': platos_disponibles,
                'cobertura_estimada_stock': cobertura_estimada_stock,
                'tendencia_consumo_semanal': tendencia_consumo_semanal,
                'tendencia_ventas_consumo': tendencia_ventas_consumo,
                'merma_por_insumo': merma_por_insumo,
                'ganancias_diarias': ganancias_diarias,
                'ganancias_semanales': ganancias_semanales,
                'ganancias_mensuales': ganancias_mensuales,
                'kpis_decision': kpis_decision,
                'analisis_complementarios': analisis_complementarios,
            }
        )


def _parse_fecha_filtro(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value).date()
    except ValueError:
        return None


def _data_mart_desactualizado():
    esperados = {
        HechoMovimientoStock.Origen.ENTRADA: DetalleEntrada.objects.count(),
        HechoMovimientoStock.Origen.SALIDA: DetalleSalida.objects.count(),
        HechoMovimientoStock.Origen.MERMA: Merma.objects.count(),
    }
    actuales = {
        item['origen']: item['total']
        for item in HechoMovimientoStock.objects.values('origen').annotate(total=Count('id_hecho_movimiento_stock'))
    }
    return any(actuales.get(origen, 0) != total for origen, total in esperados.items())


def _rango_periodo(periodo):
    hoy = timezone.localdate()
    if periodo == 'dia':
        return hoy, hoy
    if periodo == 'semana':
        inicio = hoy - timedelta(days=hoy.isoweekday() - 1)
        return inicio, inicio + timedelta(days=6)
    if periodo == 'mes':
        inicio = hoy.replace(day=1)
        siguiente = (inicio.replace(day=28) + timedelta(days=4)).replace(day=1)
        return inicio, siguiente - timedelta(days=1)
    if periodo == 'trimestre':
        primer_mes = ((hoy.month - 1) // 3) * 3 + 1
        inicio = hoy.replace(month=primer_mes, day=1)
        if primer_mes >= 10:
            siguiente = hoy.replace(year=hoy.year + 1, month=1, day=1)
        else:
            siguiente = hoy.replace(month=primer_mes + 3, day=1)
        return inicio, siguiente - timedelta(days=1)
    return None, None


def _fechas_dashboard(params):
    inicio = _parse_fecha_filtro(params.get('fecha_inicio'))
    fin = _parse_fecha_filtro(params.get('fecha_fin'))
    if not inicio and not fin:
        inicio, fin = _rango_periodo(params.get('periodo'))
    return inicio, fin


def _granularidad_tendencia(params):
    inicio, fin = _fechas_dashboard(params)
    if params.get('periodo') == 'dia':
        return 'dia'
    if inicio and fin and (fin - inicio).days <= 31:
        return 'dia'
    if (inicio and not fin) or (fin and not inicio):
        return 'dia'
    return 'semana'


def _filtrar_hechos_dashboard(hechos, params):
    inicio, fin = _fechas_dashboard(params)
    if inicio:
        hechos = hechos.filter(id_dim_tiempo__fecha__gte=inicio)
    if fin:
        hechos = hechos.filter(id_dim_tiempo__fecha__lte=fin)
    if params.get('insumo'):
        hechos = hechos.filter(id_dim_insumo__nombre__iexact=params['insumo'])
    if params.get('plato'):
        hechos = hechos.filter(plato__iexact=params['plato'])
    if params.get('tipo_dia') == 'fin_semana':
        hechos = hechos.filter(id_dim_tiempo__dia_semana__in=[6, 7])
    elif params.get('tipo_dia') == 'entre_semana':
        hechos = hechos.filter(id_dim_tiempo__dia_semana__in=[1, 2, 3, 4, 5])
    return hechos


def _filtrar_salidas_dashboard(salidas, params):
    inicio, fin = _fechas_dashboard(params)
    if inicio:
        salidas = salidas.filter(fecha_salida__date__gte=inicio)
    if fin:
        salidas = salidas.filter(fecha_salida__date__lte=fin)
    if params.get('plato'):
        salidas = salidas.filter(plato__iexact=params['plato'])
    if params.get('insumo'):
        salidas = salidas.filter(detalles__id_insumo__nombre__iexact=params['insumo']).distinct()
    if params.get('tipo_dia') == 'fin_semana':
        salidas = salidas.annotate(dia_semana=ExtractIsoWeekDay('fecha_salida')).filter(dia_semana__in=[6, 7])
    elif params.get('tipo_dia') == 'entre_semana':
        salidas = salidas.annotate(dia_semana=ExtractIsoWeekDay('fecha_salida')).filter(dia_semana__in=[1, 2, 3, 4, 5])
    return salidas


def _demanda_por_dia_franja(salidas_base=None):
    """Calcula promedio historico de platos por dia de semana y franja horaria."""
    salidas = (
        (salidas_base if salidas_base is not None else Salida.objects.all()).annotate(
            fecha=TruncDate('fecha_salida'),
            hora=ExtractHour('fecha_salida'),
            dia_semana=ExtractIsoWeekDay('fecha_salida'),
        )
        .values('fecha', 'dia_semana', 'hora', 'plato')
        .annotate(platos_dia=Sum('cantidad_platos'), registros=Count('id_salida'))
        .order_by('dia_semana', 'hora', 'plato')
    )
    acumulados = {}
    for item in salidas:
        hora = item['hora'] or 0
        clave = (item['dia_semana'], hora, item['plato'] or 'Sin plato')
        datos = acumulados.setdefault(clave, {'total_platos': Decimal('0'), 'dias': 0, 'registros': 0})
        datos['total_platos'] += item['platos_dia'] or 0
        datos['dias'] += 1
        datos['registros'] += item['registros']

    resultado = []
    for (dia_semana, hora, plato), datos in acumulados.items():
        promedio = datos['total_platos'] / datos['dias'] if datos['dias'] else Decimal('0')
        resultado.append(
            {
                'dia_semana': dia_semana,
                'nombre_dia': NOMBRES_DIA.get(dia_semana, ''),
                'hora': hora,
                'franja_horaria': f'{hora:02d}:00-{hora + 1:02d}:00',
                'plato': plato,
                'promedio_platos': promedio,
                'total_platos': datos['total_platos'],
                'dias_observados': datos['dias'],
                'registros': datos['registros'],
            }
        )

    return sorted(resultado, key=lambda item: (item['dia_semana'], item['hora'], item['plato']))


def _platos_disponibles():
    """Calcula cuantos platos se pueden preparar con el stock actual de cada insumo."""
    stocks = {
        item.nombre: getattr(item, 'stock', None).cantidad_actual if hasattr(item, 'stock') else Decimal('0')
        for item in Insumo.objects.select_related('stock').filter(estado=True)
    }
    disponibles = []

    for plato, receta in RECETAS_PLATOS.items():
        capacidades = []
        for insumo, cantidad_requerida in receta.items():
            stock_actual = stocks.get(insumo, Decimal('0'))
            capacidad = stock_actual / cantidad_requerida if cantidad_requerida else Decimal('0')
            capacidades.append(
                {
                    'insumo': insumo,
                    'stock_actual': stock_actual,
                    'cantidad_requerida': cantidad_requerida,
                    'capacidad': capacidad,
                }
            )

        limitante = min(capacidades, key=lambda item: item['capacidad']) if capacidades else None
        disponibles.append(
            {
                'plato': plato,
                'platos_enteros_disponibles': int(limitante['capacidad']) if limitante else 0,
                'insumo_limitante': limitante['insumo'] if limitante else '',
                'detalle': capacidades,
            }
        )

    return sorted(disponibles, key=lambda item: item['platos_enteros_disponibles'])


def _cobertura_estimada_stock(hechos):
    """Estima cuantos dias alcanza cada insumo segun consumo promedio historico diario."""
    consumo_diario = (
        hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
        .values('id_dim_insumo__nombre', 'id_dim_tiempo__fecha')
        .annotate(total=Sum('cantidad'))
    )
    acumulados = {}
    for item in consumo_diario:
        datos = acumulados.setdefault(item['id_dim_insumo__nombre'], {'total': Decimal('0'), 'dias': 0})
        datos['total'] += item['total'] or Decimal('0')
        datos['dias'] += 1

    stock_actual = {
        item.nombre: getattr(item, 'stock', None).cantidad_actual if hasattr(item, 'stock') else Decimal('0')
        for item in Insumo.objects.select_related('stock').filter(estado=True)
    }
    resultado = []
    for nombre, stock in stock_actual.items():
        datos = acumulados.get(nombre, {'total': Decimal('0'), 'dias': 0})
        promedio = datos['total'] / datos['dias'] if datos['dias'] else Decimal('0')
        cobertura = stock / promedio if promedio else Decimal('0')
        resultado.append(
            {
                'insumo': nombre,
                'stock_actual': stock,
                'consumo_promedio_diario': promedio,
                'cobertura_dias': cobertura,
            }
        )

    return sorted(resultado, key=lambda item: item['cobertura_dias'])


def _tendencia_consumo_semanal(hechos):
    """Compara consumo semanal actual contra la semana anterior con estadistica descriptiva."""
    semanas = list(
        hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
        .annotate(semana=TruncWeek('id_dim_tiempo__fecha'))
        .values('semana')
        .annotate(consumo=Sum('cantidad'), costo=Sum('costo_total'))
        .order_by('semana')
    )
    resultado = []
    anterior = None
    for item in semanas:
        consumo = item['consumo'] or Decimal('0')
        variacion = ((consumo - anterior) / anterior * Decimal('100')) if anterior else None
        if variacion is None:
            estado = 'sin referencia'
        elif variacion > Decimal('5'):
            estado = 'crecimiento'
        elif variacion < Decimal('-5'):
            estado = 'disminucion'
        else:
            estado = 'estable'
        resultado.append(
            {
                'semana': item['semana'],
                'consumo': consumo,
                'costo': item['costo'] or Decimal('0'),
                'variacion_porcentual': variacion,
                'estado_tendencia': estado,
            }
        )
        anterior = consumo

    return resultado


def _tendencia_ventas_consumo(hechos, ganancias_semanales, granularidad='semana', salidas_base=None):
    """Cruza ventas y consumo desde las mismas salidas filtradas para ver demanda real."""
    trunc_periodo = TruncDate if granularidad == 'dia' else TruncWeek
    if salidas_base is not None:
        salida_ids = salidas_base.values('id_salida')
        consumos_query = (
            DetalleSalida.objects
            .filter(id_salida__in=salida_ids)
            .annotate(semana=trunc_periodo('id_salida__fecha_salida'))
            .values('semana')
            .annotate(consumo=Sum('cantidad'))
        )
        costos = {
            _fecha_key(item['semana']): item['costo'] or Decimal('0')
            for item in hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
            .annotate(semana=trunc_periodo('id_dim_tiempo__fecha'))
            .values('semana')
            .annotate(costo=Sum('costo_total'))
        }
        consumos = {
            _fecha_key(item['semana']): {
                'consumo': item['consumo'] or Decimal('0'),
                'costo': costos.get(_fecha_key(item['semana']), Decimal('0')),
            }
            for item in consumos_query
        }
    else:
        consumos = {
            _fecha_key(item['semana']): {
                'consumo': item['consumo'] or Decimal('0'),
                'costo': item['costo'] or Decimal('0'),
            }
            for item in hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
            .annotate(semana=trunc_periodo('id_dim_tiempo__fecha'))
            .values('semana')
            .annotate(consumo=Sum('cantidad'), costo=Sum('costo_total'))
        }
    resultado = []
    ventas_anterior = None
    consumo_anterior = None

    for item in ganancias_semanales:
        semana = _fecha_key(item['semana'])
        ventas = item['ventas'] or Decimal('0')
        consumo = consumos.get(semana, {}).get('consumo', Decimal('0'))
        costo = consumos.get(semana, {}).get('costo', Decimal('0'))
        variacion_ventas = ((ventas - ventas_anterior) / ventas_anterior * Decimal('100')) if ventas_anterior else None
        variacion_consumo = (
            (consumo - consumo_anterior) / consumo_anterior * Decimal('100')
            if consumo_anterior else None
        )

        if variacion_ventas is None:
            estado = 'sin referencia'
        elif variacion_ventas > Decimal('5'):
            estado = 'crecimiento'
        elif variacion_ventas < Decimal('-5'):
            estado = 'disminucion'
        else:
            estado = 'estable'

        resultado.append(
            {
                'semana': item['semana'],
                'ventas': ventas,
                'consumo': consumo,
                'costo': costo,
                'ganancia': item['ganancia'] or Decimal('0'),
                'platos': item['platos'] or Decimal('0'),
                'variacion_ventas': variacion_ventas,
                'variacion_consumo': variacion_consumo,
                'estado_tendencia': estado,
                'granularidad': granularidad,
            }
        )
        ventas_anterior = ventas
        consumo_anterior = consumo

    return resultado


def _fecha_key(value):
    """Normaliza date/datetime para cruzar costos del Data Mart con ventas operativas."""
    return value.date() if hasattr(value, 'date') else value


def _merma_por_insumo(hechos):
    """Agrupa las mermas por insumo para el indicador de perdidas."""
    return list(
        hechos.filter(id_dim_tipo_movimiento__nombre='Merma')
        .values('id_dim_insumo__nombre', 'id_dim_insumo__unidad_medida')
        .annotate(cantidad=Sum('cantidad'), costo=Sum('costo_total'))
        .order_by('-cantidad')
    )


def _ultimos_hechos_por_insumo(hechos):
    """Devuelve el ultimo hecho cronologico por insumo para leer stock vigente."""
    ultimos = {}
    for hecho in hechos.order_by(
        'id_dim_insumo__nombre',
        'id_dim_tiempo__fecha',
        'id_dim_tiempo__hora',
        'id_hecho_movimiento_stock',
    ).values(
        'id_dim_insumo__nombre',
        'id_dim_insumo__categoria',
        'id_dim_insumo__unidad_medida',
        'id_dim_insumo__stock_minimo',
        'stock_resultante',
        'estado_stock',
        'recomendacion_compra',
    ):
        ultimos[hecho['id_dim_insumo__nombre']] = hecho
    return ultimos


def _alertas_compra_actuales(hechos):
    """Lista solo insumos cuyo ultimo stock reconstruido esta en riesgo."""
    consumos = {
        item['id_dim_insumo__nombre']: item['consumo'] or Decimal('0')
        for item in hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
        .values('id_dim_insumo__nombre')
        .annotate(consumo=Sum('cantidad'))
    }
    alertas = []

    for nombre, hecho in _ultimos_hechos_por_insumo(hechos).items():
        if hecho['estado_stock'] not in ['critico', 'preventivo']:
            continue
        alertas.append(
            {
                **hecho,
                'consumo': consumos.get(nombre, Decimal('0')),
                'ultimo_stock': hecho['stock_resultante'],
            }
        )

    prioridad = {'critico': 0, 'preventivo': 1}
    return sorted(alertas, key=lambda item: (prioridad.get(item['estado_stock'], 2), item['ultimo_stock']))[:10]


def _kpis_decision(
    resumen,
    stock_actual,
    platos_disponibles,
    demanda_por_dia_franja,
    tendencia_consumo_semanal,
    cobertura_estimada_stock,
    merma_por_insumo,
    ganancias_mensuales,
):
    """Construye los 7 KPI centrales como preguntas de toma de decision."""
    total_insumos = len(stock_actual)
    stock_riesgo = [
        item for item in stock_actual
        if Decimal(str(item['stock__cantidad_actual'] or 0)) <= Decimal(str(item['stock_minimo'] or 0))
    ]
    stock_preventivo = [
        item for item in stock_actual
        if Decimal(str(item['stock_minimo'] or 0)) > 0
        and Decimal(str(item['stock_minimo'] or 0)) < Decimal(str(item['stock__cantidad_actual'] or 0))
        <= Decimal(str(item['stock_minimo'] or 0)) * Decimal('1.25')
    ]
    plato_limitante = platos_disponibles[0] if platos_disponibles else None
    demanda_pico = max(demanda_por_dia_franja, key=lambda item: item['promedio_platos'], default=None)
    ultima_tendencia = tendencia_consumo_semanal[-1] if tendencia_consumo_semanal else None
    menor_cobertura = min(cobertura_estimada_stock, key=lambda item: item['cobertura_dias'], default=None)
    mayor_merma = merma_por_insumo[0] if merma_por_insumo else None
    total_merma = resumen.get('total_mermas', Decimal('0')) or Decimal('0')
    total_consumo = resumen.get('total_salidas', Decimal('0')) or Decimal('0')
    porcentaje_merma = (total_merma / total_consumo * Decimal('100')) if total_consumo else Decimal('0')
    if porcentaje_merma > Decimal('5'):
        estado_merma = 'critico'
        decision_merma = 'La merma es alta; revisar recepcion, manipulacion y conservacion de los insumos con mayor perdida.'
    elif porcentaje_merma > Decimal('2'):
        estado_merma = 'preventivo'
        decision_merma = 'La merma es media; controlar la recepcion y observar si se repite en los mismos insumos.'
    else:
        estado_merma = 'normal'
        decision_merma = 'La merma esta en un rango bajo para el periodo filtrado.'
    meta_ventas = _meta_ventas_mensual(ganancias_mensuales)
    nivel_ventas = _nivel_ventas_mensual(ganancias_mensuales)
    mes_actual = ganancias_mensuales[-1] if ganancias_mensuales else {}
    ventas_actuales = mes_actual.get('ventas', Decimal('0')) or Decimal('0')
    cumplimiento_meta = (ventas_actuales / meta_ventas * Decimal('100')) if meta_ventas else Decimal('0')
    if nivel_ventas == 'alto':
        decision_meta = 'El ultimo mes fue alto; mantener stock y preparacion para los horarios de mayor demanda.'
    elif nivel_ventas == 'bajo':
        decision_meta = 'El ultimo mes fue bajo; revisar platos con menor salida, horarios y disponibilidad de insumos.'
    else:
        decision_meta = 'El ultimo mes fue normal; sostener compras y preparacion segun la demanda registrada.'

    return [
        {
            'codigo': 'stock_minimo',
            'nombre': 'Stock actual frente al minimo',
            'pregunta': 'Que insumos debo reponer primero?',
            'valor': len(stock_riesgo) + len(stock_preventivo),
            'unidad': 'insumos en riesgo',
            'lectura': (
                f'{len(stock_riesgo)} insumos estan en minimo o por debajo y '
                f'{len(stock_preventivo)} estan cerca del minimo.'
            ),
            'decision': 'Priorizar compra inmediata de insumos criticos y reponer preventivamente los cercanos al minimo.',
            'estado': 'critico' if stock_riesgo else ('preventivo' if stock_preventivo else 'normal'),
        },
        {
            'codigo': 'platos_disponibles',
            'nombre': 'Platos disponibles',
            'pregunta': 'Cuantos pedidos se pueden atender con el stock actual?',
            'valor': plato_limitante['platos_enteros_disponibles'] if plato_limitante else 0,
            'unidad': 'platos del tipo mas limitado',
            'lectura': (
                f"{plato_limitante['plato']} limita la produccion por {plato_limitante['insumo_limitante']}."
                if plato_limitante else 'No hay salidas suficientes para calcular disponibilidad.'
            ),
            'decision': 'Reponer el insumo limitante antes de ofrecer mayor volumen de ese plato.',
            'estado': 'critico' if plato_limitante and plato_limitante['platos_enteros_disponibles'] <= 10 else 'normal',
        },
        {
            'codigo': 'demanda_franja',
            'nombre': 'Demanda promedio por dia y franja horaria',
            'pregunta': 'Cuando se debe preparar mas stock operativo?',
            'valor': demanda_pico['promedio_platos'] if demanda_pico else 0,
            'unidad': 'platos promedio',
            'lectura': (
                f"{demanda_pico['nombre_dia']} {demanda_pico['franja_horaria']} concentra la mayor demanda de {demanda_pico['plato']}."
                if demanda_pico else 'No hay ventas registradas para estimar demanda.'
            ),
            'decision': 'Planificar preparacion y compras antes de la franja de mayor demanda.',
            'estado': 'normal',
        },
        {
            'codigo': 'tendencia_ventas_consumo',
            'nombre': 'Variacion y tendencia de ventas/consumo',
            'pregunta': 'La demanda sube, baja o se mantiene?',
            'valor': ultima_tendencia['variacion_ventas'] if ultima_tendencia else None,
            'unidad': '% variacion semanal',
            'lectura': (
                f"Las ventas semanales estan en estado {ultima_tendencia['estado_tendencia']}."
                if ultima_tendencia else 'No hay semanas suficientes para comparar tendencia.'
            ),
            'decision': 'Ajustar cantidades de compra si la tendencia crece o baja de forma sostenida.',
            'estado': ultima_tendencia['estado_tendencia'] if ultima_tendencia else 'sin referencia',
        },
        {
            'codigo': 'cobertura_riesgo',
            'nombre': 'Cobertura y riesgo de desabastecimiento',
            'pregunta': 'Cuantos dias alcanza el stock disponible?',
            'valor': menor_cobertura['cobertura_dias'] if menor_cobertura else 0,
            'unidad': 'dias',
            'lectura': (
                f"{menor_cobertura['insumo']} tiene la menor cobertura estimada."
                if menor_cobertura else 'No hay consumo historico para estimar cobertura.'
            ),
            'decision': 'Comprar primero los insumos con menor cobertura de dias.',
            'estado': 'critico' if menor_cobertura and menor_cobertura['cobertura_dias'] <= 2 else 'normal',
        },
        {
            'codigo': 'merma_insumo',
            'nombre': 'Merma por insumo',
            'pregunta': 'Donde se estan generando perdidas?',
            'valor': total_merma,
            'unidad': 'kg',
            'lectura': (
                f"{mayor_merma['id_dim_insumo__nombre']} concentra la mayor merma. "
                f"La merma representa {porcentaje_merma.quantize(Decimal('0.01'))}% del consumo."
                if mayor_merma else 'No existen registros de merma en el periodo.'
            ),
            'decision': decision_merma,
            'estado': estado_merma if mayor_merma else 'normal',
            'porcentaje_consumo': porcentaje_merma,
            'costo_estimado': resumen.get('costo_merma', Decimal('0')) or Decimal('0'),
        },
        {
            'codigo': 'meta_ventas',
            'nombre': 'Cumplimiento de meta de ventas',
            'pregunta': 'Se esta cumpliendo la meta mensual de ventas?',
            'valor': cumplimiento_meta,
            'unidad': '%',
            'lectura': (
                f"El ultimo mes fue {nivel_ventas}; ventas Bs {ventas_actuales.quantize(Decimal('0.01'))} "
                f"contra meta estimada Bs {meta_ventas.quantize(Decimal('0.01'))}."
            ),
            'decision': decision_meta,
            'estado': 'normal' if cumplimiento_meta >= 100 else ('critico' if nivel_ventas == 'bajo' else 'preventivo'),
            'nivel_ventas': nivel_ventas,
        },
    ]


def _meta_ventas_mensual(ganancias_mensuales):
    ventas = [item['ventas'] or Decimal('0') for item in ganancias_mensuales if item.get('ventas')]
    if not ventas:
        return Decimal('0')
    return (sum(ventas, Decimal('0')) / len(ventas)) * META_VENTAS_FACTOR


def _nivel_ventas_mensual(ganancias_mensuales):
    ventas = [item['ventas'] or Decimal('0') for item in ganancias_mensuales if item.get('ventas')]
    if len(ventas) < 2:
        return 'normal'
    promedio = sum(ventas, Decimal('0')) / len(ventas)
    ultimo_mes = ventas[-1]
    if promedio <= 0:
        return 'normal'
    if ultimo_mes < promedio * Decimal('0.85'):
        return 'bajo'
    if ultimo_mes > promedio * Decimal('1.15'):
        return 'alto'
    return 'normal'


def _analisis_complementarios(
    consumo_por_insumo,
    tendencia,
    demanda_por_dia_franja,
    ganancias_mensuales,
    compras_mensual,
):
    """Resume lecturas secundarias que explican los KPI principales."""
    producto_mas_consumido = consumo_por_insumo[0] if consumo_por_insumo else None
    demanda_pico = max(demanda_por_dia_franja, key=lambda item: item['promedio_platos'], default=None)
    ultimo_mes = ganancias_mensuales[-1] if ganancias_mensuales else None
    proyeccion_mes = _proyectar_siguiente_mes(ganancias_mensuales)
    tendencia_costos = _tendencia_costos_abastecimiento(compras_mensual)
    entradas_vs_salidas = _entradas_vs_salidas(tendencia)
    lectura_abastecimiento = _lectura_abastecimiento(entradas_vs_salidas, tendencia_costos)

    return {
        'proyeccion_proximo_mes': proyeccion_mes,
        'tendencia_costos_abastecimiento': tendencia_costos,
        'entradas_vs_salidas': entradas_vs_salidas,
        'lectura_abastecimiento': lectura_abastecimiento,
        'producto_mas_consumido': producto_mas_consumido,
        'dia_mayor_demanda': demanda_pico['nombre_dia'] if demanda_pico else '',
        'franja_horaria_mayor_demanda': demanda_pico['franja_horaria'] if demanda_pico else '',
        'plato_mayor_demanda': demanda_pico['plato'] if demanda_pico else '',
        'ventas_ultimo_mes': ultimo_mes['ventas'] if ultimo_mes else Decimal('0'),
    }


def _proyectar_siguiente_mes(ganancias_mensuales):
    if not ganancias_mensuales:
        return {
            'ventas_estimadas': Decimal('0'),
            'ganancia_estimada': Decimal('0'),
            'variacion_vs_ultimo_mes': None,
            'lectura': 'Todavia no hay datos historicos suficientes para estimar ventas y ganancia del siguiente mes.',
            'decision': 'Registrar mas ventas y salidas para que la proyeccion sea representativa.',
            'metodo': 'Sin datos historicos.',
        }

    ultimos = ganancias_mensuales[-3:]
    ventas = [item['ventas'] or Decimal('0') for item in ultimos]
    ganancias = [item['ganancia'] or Decimal('0') for item in ultimos]
    ventas_estimadas = sum(ventas, Decimal('0')) / len(ventas)
    ganancia_estimada = sum(ganancias, Decimal('0')) / len(ganancias)
    ultimo_mes = ganancias_mensuales[-1]['ventas'] or Decimal('0')
    variacion = ((ventas_estimadas - ultimo_mes) / ultimo_mes * Decimal('100')) if ultimo_mes else None

    if variacion is None:
        lectura = 'Estimacion futura basada en los meses disponibles, sin comparacion contra el ultimo mes.'
        decision = 'Usar esta estimacion como referencia inicial y seguir cargando ventas reales.'
    elif variacion > Decimal('5'):
        lectura = 'La estimacion del proximo mes muestra crecimiento frente al ultimo mes registrado.'
        decision = 'Reforzar compras y preparacion de los insumos con mayor consumo antes de los dias pico.'
    elif variacion < Decimal('-5'):
        lectura = 'La estimacion del proximo mes muestra una posible baja frente al ultimo mes registrado.'
        decision = 'Evitar compras excesivas y revisar platos, horarios o dias con menor demanda.'
    else:
        lectura = 'La estimacion del proximo mes se mantiene estable frente al ultimo mes registrado.'
        decision = 'Mantener el ritmo de abastecimiento y vigilar cambios en costos o stock critico.'

    return {
        'ventas_estimadas': ventas_estimadas,
        'ganancia_estimada': ganancia_estimada,
        'variacion_vs_ultimo_mes': variacion,
        'lectura': lectura,
        'decision': decision,
        'metodo': 'Estimacion con promedio movil de los ultimos tres meses disponibles.',
    }


def _tendencia_costos_abastecimiento(compras_mensual):
    if len(compras_mensual) < 2:
        return {'estado': 'sin referencia', 'variacion_porcentual': None}
    actual = compras_mensual[-1]['costo'] or Decimal('0')
    anterior = compras_mensual[-2]['costo'] or Decimal('0')
    variacion = ((actual - anterior) / anterior * Decimal('100')) if anterior else None
    if variacion is None:
        estado = 'sin referencia'
    elif variacion > Decimal('5'):
        estado = 'sube'
    elif variacion < Decimal('-5'):
        estado = 'baja'
    else:
        estado = 'estable'
    return {'estado': estado, 'variacion_porcentual': variacion, 'costo_actual': actual, 'costo_anterior': anterior}


def _entradas_vs_salidas(tendencia):
    total_entradas = sum(
        (item['total'] or Decimal('0')) for item in tendencia
        if item['id_dim_tipo_movimiento__nombre'] == 'Entrada'
    )
    total_salidas = sum(
        (item['total'] or Decimal('0')) for item in tendencia
        if item['id_dim_tipo_movimiento__nombre'] == 'Salida'
    )
    balance = total_entradas - total_salidas
    return {'entradas': total_entradas, 'salidas': total_salidas, 'balance': balance}


def _lectura_abastecimiento(entradas_vs_salidas, tendencia_costos):
    balance = entradas_vs_salidas['balance']
    estado_costos = tendencia_costos.get('estado', 'sin referencia')

    if balance > 0:
        lectura_balance = 'Entro mas stock del que se consumio, por lo que existe un margen positivo de inventario.'
        decision_balance = 'Verificar que ese margen no genere acumulacion innecesaria ni riesgo de deterioro.'
    elif balance < 0:
        lectura_balance = 'Se consumio mas stock del que ingreso, lo que puede acercar al restaurante al desabastecimiento.'
        decision_balance = 'Priorizar compras de los insumos con menor cobertura y mayor consumo.'
    else:
        lectura_balance = 'Las entradas y salidas estan equilibradas.'
        decision_balance = 'Mantener el ritmo de compras y controlar cambios en demanda.'

    if estado_costos == 'sube':
        lectura_costos = 'Los costos de abastecimiento estan subiendo.'
        decision_costos = 'Revisar precios de compra, proveedores e insumos de mayor costo.'
    elif estado_costos == 'baja':
        lectura_costos = 'Los costos de abastecimiento estan bajando.'
        decision_costos = 'Confirmar que la baja no se deba a compras insuficientes para cubrir la demanda.'
    elif estado_costos == 'estable':
        lectura_costos = 'Los costos de abastecimiento se mantienen estables.'
        decision_costos = 'Mantener proveedores y cantidades mientras la cobertura sea suficiente.'
    else:
        lectura_costos = 'No hay meses suficientes para comparar costos.'
        decision_costos = 'Registrar mas compras para evaluar tendencia de abastecimiento.'

    return {
        'lectura': f'{lectura_balance} {lectura_costos}',
        'decision': f'{decision_balance} {decision_costos}',
    }


def _ganancias_diarias(hechos, salidas_base=None):
    """Calcula ventas, costo consumido y ganancia por dia sin duplicar ventas por detalle."""
    costos = {
        _fecha_key(item['id_dim_tiempo__fecha']): item['costo'] or Decimal('0')
        for item in hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
        .values('id_dim_tiempo__fecha')
        .annotate(costo=Sum('costo_total'))
    }
    ventas = (
        (salidas_base if salidas_base is not None else Salida.objects.all())
        .annotate(fecha=TruncDate('fecha_salida'))
        .values('fecha')
        .annotate(ventas=Sum('total_venta_estimado'), platos=Sum('cantidad_platos'))
        .order_by('fecha')
    )

    return [
        {
            'fecha': item['fecha'],
            'ventas': item['ventas'] or Decimal('0'),
            'costo': costos.get(_fecha_key(item['fecha']), Decimal('0')),
            'ganancia': (item['ventas'] or Decimal('0')) - costos.get(_fecha_key(item['fecha']), Decimal('0')),
            'platos': item['platos'] or Decimal('0'),
        }
        for item in ventas
    ]


def _ganancias_semanales(hechos, salidas_base=None, granularidad='semana'):
    """Calcula utilidad por dia o semana comparando ventas estimadas contra costo consumido."""
    trunc_periodo = TruncDate if granularidad == 'dia' else TruncWeek
    costos = {
        _fecha_key(item['semana']): item['costo'] or Decimal('0')
        for item in hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
        .annotate(semana=trunc_periodo('id_dim_tiempo__fecha'))
        .values('semana')
        .annotate(costo=Sum('costo_total'))
    }
    ventas = (
        (salidas_base if salidas_base is not None else Salida.objects.all())
        .annotate(semana=trunc_periodo('fecha_salida'))
        .values('semana')
        .annotate(ventas=Sum('total_venta_estimado'), platos=Sum('cantidad_platos'))
        .order_by('semana')
    )

    return [
        {
            'semana': item['semana'],
            'ventas': item['ventas'] or Decimal('0'),
            'costo': costos.get(_fecha_key(item['semana']), Decimal('0')),
            'ganancia': (item['ventas'] or Decimal('0')) - costos.get(_fecha_key(item['semana']), Decimal('0')),
            'platos': item['platos'] or Decimal('0'),
            'granularidad': granularidad,
        }
        for item in ventas
    ]


def _ganancias_mensuales(hechos, salidas_base=None):
    """Calcula utilidad mensual usando ventas operativas y costos del Data Mart."""
    costos = {
        _fecha_key(item['mes']): item['costo'] or Decimal('0')
        for item in hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
        .annotate(mes=TruncMonth('id_dim_tiempo__fecha'))
        .values('mes')
        .annotate(costo=Sum('costo_total'))
    }
    ventas = (
        (salidas_base if salidas_base is not None else Salida.objects.all())
        .annotate(mes=TruncMonth('fecha_salida'))
        .values('mes')
        .annotate(ventas=Sum('total_venta_estimado'), platos=Sum('cantidad_platos'))
        .order_by('mes')
    )

    return [
        {
            'mes': item['mes'],
            'ventas': item['ventas'] or Decimal('0'),
            'costo': costos.get(_fecha_key(item['mes']), Decimal('0')),
            'ganancia': (item['ventas'] or Decimal('0')) - costos.get(_fecha_key(item['mes']), Decimal('0')),
            'platos': item['platos'] or Decimal('0'),
        }
        for item in ventas
    ]


def _costos_promedio_por_insumo():
    """Calcula costo promedio de compra por insumo usando entradas registradas."""
    costos = {}
    acumulados = {}

    for entrada in Entrada.objects.prefetch_related('detalles').all():
        for detalle in entrada.detalles.all():
            cantidad, costo = acumulados.get(detalle.id_insumo_id, (Decimal('0'), Decimal('0')))
            acumulados[detalle.id_insumo_id] = (
                cantidad + detalle.cantidad,
                costo + (detalle.cantidad * detalle.costo_unitario),
            )

    for insumo_id, (cantidad, costo) in acumulados.items():
        costos[insumo_id] = costo / cantidad if cantidad else Decimal('0')

    return costos


def _valor_invertido_stock():
    """Calcula el dinero invertido en stock actual con costos promedio."""
    costos = _costos_promedio_por_insumo()
    total = Decimal('0')

    for insumo in Insumo.objects.select_related('stock').filter(estado=True):
        stock = getattr(insumo, 'stock', None)
        if stock:
            total += stock.cantidad_actual * costos.get(insumo.id_insumo, Decimal('0'))

    return total


def _rotacion_por_insumo(hechos):
    """Calcula rotacion comparando consumo total contra stock actual reconstruido."""
    consumos = {
        item['id_dim_insumo__nombre']: item['total']
        for item in hechos.filter(id_dim_tipo_movimiento__nombre='Salida')
        .values('id_dim_insumo__nombre')
        .annotate(total=Sum('cantidad'))
    }
    ultimos = _ultimos_hechos_por_insumo(hechos)
    rotacion = []

    for nombre, consumo in consumos.items():
        ultimo = ultimos.get(nombre, {})
        referencia_stock = ultimo.get('stock_resultante') or Decimal('0')
        indice = consumo / referencia_stock if referencia_stock else Decimal('0')
        rotacion.append(
            {
                'insumo': nombre,
                'consumo': consumo,
                'stock_referencia': referencia_stock,
                'indice_rotacion': indice,
                'estado_stock': ultimo.get('estado_stock', 'normal'),
                'recomendacion_compra': ultimo.get('recomendacion_compra', 'Compra normal'),
            }
        )

    return sorted(rotacion, key=lambda item: item['indice_rotacion'], reverse=True)
