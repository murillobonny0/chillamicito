from django.db import transaction
from decimal import Decimal, InvalidOperation
from rest_framework.response import Response

from .models import Stock, Usuario


def mismo_payload(payload, guardado):
    """Compara los campos enviados, admitiendo decimales JSON como texto o numero."""
    if isinstance(payload, dict):
        return isinstance(guardado, dict) and all(
            key not in guardado or mismo_payload(value, guardado[key])
            for key, value in payload.items()
        )
    if isinstance(payload, list):
        return isinstance(guardado, list) and len(payload) == len(guardado) and all(
            mismo_payload(a, b) for a, b in zip(payload, guardado)
        )
    if payload == guardado:
        return True
    try:
        return Decimal(str(payload)) == Decimal(str(guardado))
    except InvalidOperation:
        return False


class MovimientoCreateMixin:
    """Reintenta movimientos sin aplicar dos veces su efecto sobre el stock."""

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        # Serializa reintentos del mismo usuario, incluso desde varias pestanas.
        Usuario.objects.select_for_update().get(pk=request.user.pk)
        operation_id = request.data.get('id_operacion')
        if isinstance(operation_id, str) and operation_id.strip():
            existing = self.get_queryset().filter(id_operacion=operation_id.strip()).first()
            if existing:
                if existing.id_usuario_id != request.user.pk:
                    return Response({'detail': 'El identificador de operacion ya esta en uso.'}, status=409)
                data = self.get_serializer(existing).data
                if not mismo_payload(request.data, data):
                    return Response({'detail': 'La operacion ya fue registrada con otros datos.'}, status=409)
                return Response(data)

        # La validacion y el descuento deben observar el mismo stock en PostgreSQL.
        list(Stock.objects.select_for_update().order_by('pk'))
        return super().create(request, *args, **kwargs)
