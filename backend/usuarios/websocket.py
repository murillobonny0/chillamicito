from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


def enviar_notificacion_stock(notificacion):
    """Publica una notificacion en el grupo WebSocket para avisar al frontend."""
    channel_layer = get_channel_layer()

    if not channel_layer:
        return

    # group_send llama al metodo notificacion_stock del consumer conectado.
    async_to_sync(channel_layer.group_send)(
        'notificaciones_stock',
        {
            'type': 'notificacion_stock',
            'data': {
                'id_notificacion': notificacion.id_notificacion,
                'id_insumo': notificacion.id_insumo_id,
                'id_feriado': notificacion.id_feriado_id,
                'insumo': notificacion.id_insumo.nombre if notificacion.id_insumo else '',
                'feriado': notificacion.id_feriado.nombre if notificacion.id_feriado else '',
                'fecha_feriado': notificacion.id_feriado.fecha.isoformat() if notificacion.id_feriado else None,
                'mensaje': notificacion.mensaje,
                'fecha': notificacion.fecha.isoformat(),
                'estado': notificacion.estado,
                'tipo': notificacion.tipo,
            },
        },
    )


def enviar_movimiento_stock(movimiento, tipo):
    """Publica un movimiento para refrescar el stock de los clientes conectados."""
    channel_layer = get_channel_layer()

    if not channel_layer:
        return

    fecha = getattr(movimiento, 'fecha_entrada', None) or getattr(movimiento, 'fecha_salida', None) or getattr(movimiento, 'fecha_merma', None)
    identificador = getattr(movimiento, 'id_entrada', None) or getattr(movimiento, 'id_salida', None) or getattr(movimiento, 'id_merma', None)
    async_to_sync(channel_layer.group_send)(
        'notificaciones_stock',
        {
            'type': 'movimiento_stock',
            'data': {
                'evento': 'movimiento_stock',
                'tipo': tipo,
                'id': identificador,
                'fecha': fecha.isoformat() if fecha else None,
                'mensaje': f'Se registro una nueva {tipo} de stock.',
            },
        },
    )
