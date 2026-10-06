from decimal import Decimal
from decimal import ROUND_HALF_UP

from django.db import transaction
from django.utils import timezone

from .models import (
    DetalleEntrada,
    DetalleSalida,
    DimCategoria,
    DimInsumo,
    DimTiempo,
    DimTipoMovimiento,
    DimUsuario,
    HechoMovimientoStock,
    Insumo,
    Merma,
    RegistroETL,
)

MESES = {
    1: 'Enero',
    2: 'Febrero',
    3: 'Marzo',
    4: 'Abril',
    5: 'Mayo',
    6: 'Junio',
    7: 'Julio',
    8: 'Agosto',
    9: 'Septiembre',
    10: 'Octubre',
    11: 'Noviembre',
    12: 'Diciembre',
}

DIAS_SEMANA = {
    1: 'Lunes',
    2: 'Martes',
    3: 'Miercoles',
    4: 'Jueves',
    5: 'Viernes',
    6: 'Sabado',
    7: 'Domingo',
}

DEMANDA_POR_MES = {
    4: ('bajo', 'Mes de menor movimiento esperado.'),
    5: ('bajo', 'Mes de menor movimiento esperado.'),
    6: ('bajo', 'Mes de menor movimiento esperado.'),
    8: ('alto', 'Fiestas patrias y mayor actividad social.'),
    9: ('alto', 'Aniversario de Cochabamba y eventos sociales.'),
    11: ('alto', 'Promociones y eventos previos a fin de anio.'),
    12: ('alto', 'Graduaciones, fin de anio y reuniones.'),
}

TAMANO_LOTE_BULK = 500
CENTAVOS = Decimal('0.01')


def ejecutar_etl_movimientos_stock():
    """Reconstruye el Data Mart con un proceso ETL desarrollado en Python."""
    registro = RegistroETL.objects.create(
        estado=RegistroETL.Estado.PENDIENTE,
        descripcion='ETL Python iniciado para limpiar y recargar el Data Mart.',
    )

    try:
        with transaction.atomic():
            # Se limpia el Data Mart para recargarlo con datos actualizados y consistentes.
            HechoMovimientoStock.objects.all().delete()
            DimTipoMovimiento.objects.all().delete()
            DimUsuario.objects.all().delete()
            DimTiempo.objects.all().delete()
            DimInsumo.objects.all().delete()
            DimCategoria.objects.all().delete()

            tipo_entrada = DimTipoMovimiento.objects.create(
                nombre='Entrada',
                descripcion='Ingreso de insumos al almacen.',
            )
            tipo_salida = DimTipoMovimiento.objects.create(
                nombre='Salida',
                descripcion='Consumo o descuento de insumos del almacen.',
            )
            tipo_merma = DimTipoMovimiento.objects.create(
                nombre='Merma',
                descripcion='Perdida manual de insumos no asociada a ventas.',
            )

            resultado = _cargar_movimientos_cronologicos(tipo_entrada, tipo_salida, tipo_merma)

            registro.estado = RegistroETL.Estado.EJECUTADO
            registro.descripcion = (
                'ETL Python ejecutado correctamente. '
                f"Entradas: {resultado['entradas']}; salidas: {resultado['salidas']}; "
                f"mermas: {resultado['mermas']}; "
                f"movimientos cargados: {resultado['movimientos']}. "
                f"Filas omitidas por cantidad invalida: {resultado['filas_omitidas']}. "
                f"Alertas de stock negativo: {resultado['alertas_stock_negativo']}. "
                f"Salidas costeadas en 0 por falta de historial de compra: "
                f"{resultado['salidas_sin_costo']}."
            )
            registro.save(update_fields=['estado', 'descripcion'])

        return {
            'estado': registro.estado,
            'descripcion': registro.descripcion,
            **resultado,
        }
    except Exception as exc:
        registro.estado = RegistroETL.Estado.ERROR
        registro.descripcion = f'Error durante el ETL: {exc}'
        registro.save(update_fields=['estado', 'descripcion'])
        raise


def _cargar_movimientos_cronologicos(tipo_entrada, tipo_salida, tipo_merma):
    """Recorre entradas y salidas en orden cronologico, calcula costeo promedio
    ponderado (WAC) y stock resultante insumo por insumo, y carga los hechos
    del Data Mart en lotes para un buen rendimiento y un analisis consistente.
    """
    entradas = (
        DetalleEntrada.objects.select_related(
            'id_entrada__id_usuario__id_rol',
            'id_insumo__id_categoria',
            'id_insumo__id_unidad',
        )
        .order_by('id_entrada__fecha_entrada', 'id_detalle_entrada')
    )
    salidas = (
        DetalleSalida.objects.select_related(
            'id_salida__id_usuario__id_rol',
            'id_insumo__id_categoria',
            'id_insumo__id_unidad',
        )
        .order_by('id_salida__fecha_salida', 'id_detalle_salida')
    )
    mermas = (
        Merma.objects.select_related(
            'id_usuario__id_rol',
            'id_insumo__id_categoria',
            'id_insumo__id_unidad',
        )
        .order_by('fecha_merma', 'id_merma')
    )

    movimientos = [
        (detalle.id_entrada.fecha_entrada, 1, detalle.id_detalle_entrada, 'entrada', detalle)
        for detalle in entradas
    ] + [
        (detalle.id_salida.fecha_salida, 2, detalle.id_detalle_salida, 'salida', detalle)
        for detalle in salidas
    ] + [
        (merma.fecha_merma, 3, merma.id_merma, 'merma', merma)
        for merma in mermas
    ]
    movimientos.sort(key=lambda item: (item[0], item[1], item[2]))

    # Caches en memoria: las dimensiones ya se vaciaron al iniciar el ETL, asi
    # que basta con crearlas una sola vez por valor distinto y reutilizarlas,
    # en vez de golpear la base de datos en cada movimiento.
    cache_categorias = {}
    cache_insumos = {}
    cache_tiempos = {}
    cache_usuarios = {}

    # Estado de costeo promedio ponderado (WAC) y stock corriente por insumo,
    # calculado en el mismo recorrido cronologico para evitar que una salida
    # se costee con compras que todavia no habian ocurrido.
    stock_actual = {}
    costo_promedio_actual = {}

    _precargar_dimensiones_insumos_activos(cache_categorias, cache_insumos)

    hechos_pendientes = []
    total_entradas = 0
    total_salidas = 0
    total_mermas = 0
    filas_omitidas = 0
    alertas_stock_negativo = 0
    salidas_sin_costo = 0

    for _, _, _, origen, detalle in movimientos:
        if detalle.cantidad <= 0:
            filas_omitidas += 1
            continue

        insumo_id = detalle.id_insumo_id
        stock_previo = stock_actual.get(insumo_id, Decimal('0'))

        if origen == 'entrada':
            stock_nuevo, costo_promedio = _actualizar_costeo_por_entrada(
                stock_previo,
                costo_promedio_actual.get(insumo_id, Decimal('0')),
                detalle,
            )
            stock_actual[insumo_id] = stock_nuevo
            costo_promedio_actual[insumo_id] = costo_promedio

            hechos_pendientes.append(
                _construir_hecho_entrada(
                    detalle,
                    tipo_entrada,
                    stock_nuevo,
                    cache_categorias,
                    cache_insumos,
                    cache_tiempos,
                    cache_usuarios,
                )
            )
            total_entradas += 1
            continue

        costo_unitario = costo_promedio_actual.get(insumo_id, Decimal('0'))
        if costo_unitario == 0:
            salidas_sin_costo += 1

        stock_nuevo = stock_previo - detalle.cantidad
        if stock_nuevo < 0:
            alertas_stock_negativo += 1
        stock_actual[insumo_id] = stock_nuevo

        if origen == 'salida':
            hechos_pendientes.append(
                _construir_hecho_salida(
                    detalle,
                    tipo_salida,
                    stock_nuevo,
                    costo_unitario,
                    cache_categorias,
                    cache_insumos,
                    cache_tiempos,
                    cache_usuarios,
                )
            )
            total_salidas += 1
        else:
            hechos_pendientes.append(
                _construir_hecho_merma(
                    detalle,
                    tipo_merma,
                    stock_nuevo,
                    costo_unitario,
                    cache_categorias,
                    cache_insumos,
                    cache_tiempos,
                    cache_usuarios,
                )
            )
            total_mermas += 1

    _distribuir_metricas_de_salida(hechos_pendientes)
    HechoMovimientoStock.objects.bulk_create(hechos_pendientes, batch_size=TAMANO_LOTE_BULK)

    return {
        'entradas': total_entradas,
        'salidas': total_salidas,
        'mermas': total_mermas,
        'movimientos': total_entradas + total_salidas + total_mermas,
        'filas_omitidas': filas_omitidas,
        'alertas_stock_negativo': alertas_stock_negativo,
        'salidas_sin_costo': salidas_sin_costo,
    }


def _actualizar_costeo_por_entrada(stock_previo, costo_previo, detalle):
    """Recalcula el costo promedio ponderado (WAC) del insumo al momento de la
    compra: el nuevo costo mezcla el valor del stock que ya habia con el valor
    recien comprado, tal como se costea un inventario en la practica contable.
    """
    valor_previo = stock_previo * costo_previo if stock_previo > 0 else Decimal('0')
    valor_entrada = detalle.cantidad * detalle.costo_unitario
    stock_nuevo = stock_previo + detalle.cantidad

    if stock_nuevo > 0:
        costo_promedio = (valor_previo + valor_entrada) / stock_nuevo
    else:
        costo_promedio = detalle.costo_unitario

    return stock_nuevo, costo_promedio


def _construir_hecho_entrada(
    detalle,
    tipo_movimiento,
    stock_resultante,
    cache_categorias,
    cache_insumos,
    cache_tiempos,
    cache_usuarios,
):
    """Arma (sin guardar) el hecho analitico de una compra o ingreso de insumos."""
    estado_stock, recomendacion = _evaluacion_stock(detalle.id_insumo, stock_resultante)
    return HechoMovimientoStock(
        id_dim_insumo=_dim_insumo(detalle.id_insumo, cache_insumos),
        id_dim_categoria=_dim_categoria(detalle.id_insumo.id_categoria, cache_categorias),
        id_dim_tiempo=_dim_tiempo(detalle.id_entrada.fecha_entrada, cache_tiempos),
        id_dim_usuario=_dim_usuario(detalle.id_entrada.id_usuario, cache_usuarios),
        id_dim_tipo_movimiento=tipo_movimiento,
        origen=HechoMovimientoStock.Origen.ENTRADA,
        id_origen_detalle=detalle.id_detalle_entrada,
        cantidad=detalle.cantidad,
        # Monto de compra : cantidad ingresada multiplicada por costo unitario.
        costo_total=detalle.cantidad * detalle.costo_unitario,
        stock_resultante=stock_resultante,
        estado_stock=estado_stock,
        recomendacion_compra=recomendacion,
    )


def _construir_hecho_salida(
    detalle,
    tipo_movimiento,
    stock_resultante,
    costo_unitario,
    cache_categorias,
    cache_insumos,
    cache_tiempos,
    cache_usuarios,
):
    """Arma el hecho analitico de un consumo, costeado con el
    promedio ponderado vigente para el insumo en ese momento del recorrido.
    """
    estado_stock, recomendacion = _evaluacion_stock(detalle.id_insumo, stock_resultante)
    hecho = HechoMovimientoStock(
        id_dim_insumo=_dim_insumo(detalle.id_insumo, cache_insumos),
        id_dim_categoria=_dim_categoria(detalle.id_insumo.id_categoria, cache_categorias),
        id_dim_tiempo=_dim_tiempo(detalle.id_salida.fecha_salida, cache_tiempos),
        id_dim_usuario=_dim_usuario(detalle.id_salida.id_usuario, cache_usuarios),
        id_dim_tipo_movimiento=tipo_movimiento,
        origen=HechoMovimientoStock.Origen.SALIDA,
        id_origen_detalle=detalle.id_detalle_salida,
        cantidad=detalle.cantidad,
        # Costo consumido estimado: cantidad descontada multiplicada por costo promedio vigente.
        costo_total=detalle.cantidad * costo_unitario,
        stock_resultante=stock_resultante,
        estado_stock=estado_stock,
        recomendacion_compra=recomendacion,
        plato=detalle.id_salida.plato.strip(),
        tamano=detalle.id_salida.tamano,
        cantidad_platos=detalle.id_salida.cantidad_platos,
        venta_total=detalle.id_salida.total_venta_estimado,
    )
    hecho._id_salida_etl = detalle.id_salida_id
    return hecho


def _distribuir_metricas_de_salida(hechos):
    """Evita que BI duplique ventas y platos al sumar hechos por insumo.

    La tabla de hechos esta al grano detalle-insumo. Por eso la venta total de
    la salida se reparte segun la participacion del costo de cada ingrediente;
    los platos se cuentan una sola vez en el primer detalle de la salida.
    """
    grupos = {}
    for hecho in hechos:
        if hecho.origen != HechoMovimientoStock.Origen.SALIDA:
            continue
        grupos.setdefault(hecho._id_salida_etl, []).append(hecho)

    for detalles_salida in grupos.values():
        detalles_salida.sort(key=lambda item: item.id_origen_detalle)
        venta_total = detalles_salida[0].venta_total or Decimal('0')
        cantidad_platos = detalles_salida[0].cantidad_platos
        costo_total_salida = sum((item.costo_total or Decimal('0') for item in detalles_salida), Decimal('0'))
        venta_asignada = Decimal('0')

        for index, hecho in enumerate(detalles_salida):
            hecho.cantidad_platos = cantidad_platos if index == 0 else 0
            if venta_total <= 0:
                hecho.venta_total = Decimal('0')
                continue

            if costo_total_salida > 0 and index < len(detalles_salida) - 1:
                proporcion = (hecho.costo_total or Decimal('0')) / costo_total_salida
                hecho.venta_total = (venta_total * proporcion).quantize(CENTAVOS, rounding=ROUND_HALF_UP)
                venta_asignada += hecho.venta_total
            elif costo_total_salida > 0:
                hecho.venta_total = venta_total - venta_asignada
            else:
                hecho.venta_total = venta_total if index == 0 else Decimal('0')


def _construir_hecho_merma(
    merma,
    tipo_movimiento,
    stock_resultante,
    costo_unitario,
    cache_categorias,
    cache_insumos,
    cache_tiempos,
    cache_usuarios,
):
    """Arma el hecho analitico de una perdida registrada manualmente."""
    estado_stock, recomendacion = _evaluacion_stock(merma.id_insumo, stock_resultante)
    return HechoMovimientoStock(
        id_dim_insumo=_dim_insumo(merma.id_insumo, cache_insumos),
        id_dim_categoria=_dim_categoria(merma.id_insumo.id_categoria, cache_categorias),
        id_dim_tiempo=_dim_tiempo(merma.fecha_merma, cache_tiempos),
        id_dim_usuario=_dim_usuario(merma.id_usuario, cache_usuarios),
        id_dim_tipo_movimiento=tipo_movimiento,
        origen=HechoMovimientoStock.Origen.MERMA,
        id_origen_detalle=merma.id_merma,
        cantidad=merma.cantidad,
        # Costo de merma: cantidad perdida multiplicada por costo promedio vigente.
        costo_total=merma.cantidad * costo_unitario,
        stock_resultante=stock_resultante,
        estado_stock=estado_stock,
        recomendacion_compra=recomendacion,
    )


def _evaluacion_stock(insumo, stock_resultante):
    """Clasifica el stock para que Power BI muestre resultados ya interpretados."""
    minimo = insumo.stock_minimo or Decimal('0')
    if minimo and stock_resultante <= minimo:
        return 'critico', 'Compra prioritaria'
    if minimo and stock_resultante <= (minimo * Decimal('1.25')):
        return 'preventivo', 'Revisar compra'
    return 'normal', 'Compra normal'


def _dim_categoria(categoria, cache):
    """Crea o recupera (desde cache en memoria) la dimension de categoria."""
    dim = cache.get(categoria.nombre_categoria)
    if dim is None:
        dim = DimCategoria.objects.create(
            nombre_categoria=categoria.nombre_categoria,
            descripcion=categoria.descripcion,
        )
        cache[categoria.nombre_categoria] = dim
    return dim


def _dim_insumo(insumo, cache):
    """Crea o recupera (desde cache en memoria) la dimension de insumo."""
    clave = (insumo.nombre, insumo.id_categoria.nombre_categoria, insumo.id_unidad.nombre_unidad)
    dim = cache.get(clave)
    if dim is None:
        dim = DimInsumo.objects.create(
            nombre=insumo.nombre,
            descripcion=insumo.descripcion,
            categoria=insumo.id_categoria.nombre_categoria,
            unidad_medida=insumo.id_unidad.nombre_unidad,
            stock_minimo=insumo.stock_minimo,
            estado=insumo.estado,
        )
        cache[clave] = dim
    return dim


def _precargar_dimensiones_insumos_activos(cache_categorias, cache_insumos):
    """Asegura que Power BI vea tambien insumos activos sin movimientos."""
    for insumo in Insumo.objects.select_related('id_categoria', 'id_unidad').filter(estado=True):
        _dim_categoria(insumo.id_categoria, cache_categorias)
        _dim_insumo(insumo, cache_insumos)


def _dim_tiempo(momento, cache):
    """Crea o recupera (desde cache en memoria) la dimension de tiempo, usada
    para analizar por calendario y franja horaria."""
    momento_local = timezone.localtime(momento) if timezone.is_aware(momento) else momento
    fecha = momento_local.date()
    hora = momento_local.hour
    clave = (fecha, hora)

    dim = cache.get(clave)
    if dim is not None:
        return dim

    dia_semana = momento_local.isoweekday()
    nivel_demanda, motivo_demanda = DEMANDA_POR_MES.get(
        fecha.month,
        ('normal', 'Mes sin variacion especial definida.'),
    )
    dim = DimTiempo.objects.create(
        fecha=fecha,
        hora=hora,
        dia=fecha.day,
        mes=fecha.month,
        nombre_mes=MESES[fecha.month],
        trimestre=((fecha.month - 1) // 3) + 1,
        anio=fecha.year,
        # Franja usada en BI para analizar demanda por hora, por ejemplo sabado de 15:00 a 16:00.
        franja_horaria=f'{hora:02d}:00-{hora + 1:02d}:00',
        dia_semana=dia_semana,
        nombre_dia=DIAS_SEMANA[dia_semana],
        nivel_demanda=nivel_demanda,
        motivo_demanda=motivo_demanda,
    )
    cache[clave] = dim
    return dim


def _dim_usuario(usuario, cache):
    """Crea o recupera (desde cache en memoria) la dimension del usuario
    responsable del movimiento."""
    clave = (usuario.username, usuario.rol)
    dim = cache.get(clave)
    if dim is None:
        dim = DimUsuario.objects.create(
            username=usuario.username,
            rol=usuario.rol,
            nombre=usuario.first_name,
            apellido=usuario.last_name,
        )
        cache[clave] = dim
    return dim
