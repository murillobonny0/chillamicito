from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from .models import Feriado, Insumo, Notificacion, Stock
from .websocket import enviar_notificacion_stock


DIAS_ALERTA_FERIADO = 7
MARGEN_PREVENTIVO = Decimal('1.25')


def evaluar_stock_insumo(insumo, stock_actual=None, contexto=''):
    """Crea o actualiza una alerta cuando el insumo esta critico o cerca del minimo."""
    if stock_actual is None:
        stock = getattr(insumo, 'stock', None)
        stock_actual = stock.cantidad_actual if stock else Decimal('0')

    minimo = insumo.stock_minimo or Decimal('0')
    if minimo <= 0:
        _cerrar_alertas_stock_insumo(insumo)
        return None

    if stock_actual <= minimo:
        # Si el insumo pasa a critico, se cierra cualquier aviso preventivo anterior.
        _cerrar_alertas_stock_insumo(insumo, excluir_tipos=[Notificacion.Tipo.STOCK_MINIMO])
        mensaje = (
            f'{insumo.nombre} se encuentra en nivel critico: '
            f'{stock_actual} {insumo.id_unidad}. Minimo definido: {minimo} {insumo.id_unidad}. '
            'Se necesita reponer antes de registrar nuevas salidas.'
        )
        if contexto:
            mensaje = f'{mensaje} {contexto}'
        return _guardar_notificacion(
            id_insumo=insumo,
            tipo=Notificacion.Tipo.STOCK_MINIMO,
            mensaje=mensaje,
        )

    if stock_actual <= (minimo * MARGEN_PREVENTIVO):
        # Si el insumo queda preventivo, se cierra cualquier alerta critica vieja del mismo insumo.
        _cerrar_alertas_stock_insumo(insumo, excluir_tipos=[Notificacion.Tipo.STOCK_PREVENTIVO])
        mensaje = (
            f'{insumo.nombre} esta proximo al stock minimo: '
            f'{stock_actual} {insumo.id_unidad}. Minimo definido: {minimo} {insumo.id_unidad}. '
            'Prever reposicion para evitar desabastecimiento.'
        )
        if contexto:
            mensaje = f'{mensaje} {contexto}'
        return _guardar_notificacion(
            id_insumo=insumo,
            tipo=Notificacion.Tipo.STOCK_PREVENTIVO,
            mensaje=mensaje,
        )

    # Si el stock supera el margen preventivo, se cierran alertas viejas para no mostrar datos desactualizados.
    _cerrar_alertas_stock_insumo(insumo)
    return None


def evaluar_todos_los_stocks():
    """Revisa todos los stocks activos para mantener alertas actualizadas."""
    generadas = 0
    stocks = Stock.objects.select_related('id_insumo__id_unidad').filter(id_insumo__estado=True)
    for stock in stocks:
        notificacion = evaluar_stock_insumo(stock.id_insumo, stock.cantidad_actual)
        if notificacion:
            generadas += 1
    return generadas


def validar_salida_respetando_minimo(detalle_data, plato='', tamano=''):
    """Evita que una salida deje el stock por debajo del minimo configurado."""
    insumo = detalle_data['id_insumo']
    cantidad = detalle_data['cantidad']
    stock, _ = Stock.objects.get_or_create(id_insumo=insumo)
    stock_resultante = stock.cantidad_actual - cantidad
    contexto = _contexto_salida(plato=plato, tamano=tamano, cantidad=cantidad)

    if cantidad > stock.cantidad_actual:
        evaluar_stock_insumo(insumo, stock.cantidad_actual, contexto)
        return (
            False,
            f'No hay stock suficiente para {insumo.nombre}. '
            f'Disponible: {stock.cantidad_actual} {insumo.id_unidad}.',
        )

    if stock_resultante < insumo.stock_minimo:
        evaluar_stock_insumo(insumo, stock.cantidad_actual, contexto)
        return (
            False,
            f'No se puede registrar la salida de {insumo.nombre}: '
            f'quedaria en {stock_resultante} {insumo.id_unidad}, por debajo del minimo '
            f'{insumo.stock_minimo} {insumo.id_unidad}. Se necesita reponer stock.',
        )

    if stock_resultante <= insumo.stock_minimo:
        evaluar_stock_insumo(insumo, stock_resultante, contexto)

    return True, ''


def generar_alertas_feriados_proximos(feriados=None):
    """Crea recordatorios de feriados cercanos para planificar compras y produccion."""
    hoy = timezone.localdate()
    fecha_limite = hoy + timedelta(days=DIAS_ALERTA_FERIADO)
    queryset = feriados if feriados is not None else Feriado.objects.all()
    alertas_generadas = 0
    Notificacion.objects.filter(
        tipo=Notificacion.Tipo.FERIADO,
        estado=Notificacion.Estado.PENDIENTE,
        id_feriado__fecha__lt=hoy,
    ).update(estado=Notificacion.Estado.LEIDA)

    for feriado in queryset.filter(fecha__gte=hoy, fecha__lte=fecha_limite).order_by('fecha'):
        dias_restantes = (feriado.fecha - hoy).days
        if dias_restantes == 0:
            tiempo = 'hoy'
        elif dias_restantes == 1:
            tiempo = 'mañana'
        else:
            tiempo = f'en {dias_restantes} dias'

        mensaje = (
            f'Se aproxima {feriado.nombre}: {tiempo} ({feriado.fecha}). '
            'La demanda puede elevarse; prever compras, produccion e insumos criticos.'
        )
        if dias_restantes == 0:
            mensaje = (
                f'{feriado.nombre} es hoy ({feriado.fecha}). '
                'La demanda puede elevarse; revisar stock antes de iniciar produccion.'
            )

        notificacion = (
            Notificacion.objects.filter(
                id_feriado=feriado,
                tipo=Notificacion.Tipo.FERIADO,
                estado=Notificacion.Estado.PENDIENTE,
            )
            .order_by('-fecha', '-id_notificacion')
            .first()
        )
        if notificacion:
            _cerrar_duplicados_feriado(feriado, notificacion.id_notificacion)
            notificacion.mensaje = mensaje.replace('faltan 0 dias', tiempo)
            notificacion.fecha = timezone.now()
            notificacion.save(update_fields=['mensaje', 'fecha'])
        else:
            notificacion = Notificacion.objects.create(
                id_feriado=feriado,
                tipo=Notificacion.Tipo.FERIADO,
                mensaje=mensaje.replace('faltan 0 dias', tiempo),
            )
            alertas_generadas += 1
        enviar_notificacion_stock(notificacion)

    return alertas_generadas


def _guardar_notificacion(id_insumo, tipo, mensaje):
    existente = (
        Notificacion.objects.filter(
            id_insumo=id_insumo,
            tipo=tipo,
            estado=Notificacion.Estado.PENDIENTE,
        )
        .order_by('-fecha', '-id_notificacion')
        .first()
    )

    if existente:
        _cerrar_duplicados_insumo(id_insumo, tipo, existente.id_notificacion)
        existente.mensaje = mensaje
        existente.fecha = timezone.now()
        existente.save(update_fields=['mensaje', 'fecha'])
        enviar_notificacion_stock(existente)
        return existente

    notificacion = Notificacion.objects.create(
        id_insumo=id_insumo,
        tipo=tipo,
        estado=Notificacion.Estado.PENDIENTE,
        mensaje=mensaje,
    )
    enviar_notificacion_stock(notificacion)
    return notificacion


def _cerrar_duplicados_insumo(id_insumo, tipo, conservar_id):
    Notificacion.objects.filter(
        id_insumo=id_insumo,
        tipo=tipo,
        estado=Notificacion.Estado.PENDIENTE,
    ).exclude(id_notificacion=conservar_id).update(estado=Notificacion.Estado.LEIDA)


def _cerrar_duplicados_feriado(id_feriado, conservar_id):
    Notificacion.objects.filter(
        id_feriado=id_feriado,
        tipo=Notificacion.Tipo.FERIADO,
        estado=Notificacion.Estado.PENDIENTE,
    ).exclude(id_notificacion=conservar_id).update(estado=Notificacion.Estado.LEIDA)


def _cerrar_alertas_stock_insumo(id_insumo, excluir_tipos=None):
    excluir_tipos = excluir_tipos or []
    Notificacion.objects.filter(
        id_insumo=id_insumo,
        tipo__in=[
            Notificacion.Tipo.STOCK_MINIMO,
            Notificacion.Tipo.STOCK_PREVENTIVO,
            Notificacion.Tipo.AGOTADO,
            Notificacion.Tipo.STOCK_INSUFICIENTE,
        ],
        estado=Notificacion.Estado.PENDIENTE,
    ).exclude(tipo__in=excluir_tipos).update(estado=Notificacion.Estado.LEIDA)


def _contexto_salida(plato='', tamano='', cantidad=None):
    partes = []
    if plato:
        partes.append(f'Plato: {plato}.')
    if tamano:
        partes.append(f'Tamano: {tamano}.')
    if cantidad is not None:
        partes.append(f'Salida evaluada: {cantidad}.')
    return ' '.join(partes)

