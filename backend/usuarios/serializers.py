from decimal import Decimal
from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import (
    Categoria,
    DetalleEntrada,
    DetalleSalida,
    Entrada,
    Feriado,
    Insumo,
    Merma,
    Notificacion,
    Permiso,
    Rol,
    Salida,
    Stock,
    UnidadMedida,
    Usuario,
)
from .alertas import evaluar_stock_insumo, validar_salida_respetando_minimo
from .websocket import enviar_movimiento_stock


class LoginSerializer(serializers.Serializer):
    """Datos minimos que envian para iniciar sesion."""

    username = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class UsuarioSerializer(serializers.ModelSerializer):
    """Respuesta segura: no se devuelve password, solo identidad y rol."""

    nombre = serializers.CharField(source='first_name', read_only=True)
    apellido = serializers.CharField(source='last_name', read_only=True)
    id_rol = serializers.IntegerField(source='id_rol_id', read_only=True)
    rol = serializers.CharField(read_only=True)
    rol_nombre = serializers.CharField(source='get_rol_display', read_only=True)

    class Meta:
        model = Usuario
        fields = ['id_usuario', 'nombre', 'apellido', 'username', 'id_rol', 'rol', 'rol_nombre']


class RolSerializer(serializers.ModelSerializer):
    """Convierte roles a JSON e incluye la lista de permisos asignados."""

    nombre_display = serializers.CharField(source='get_nombre_rol_display', read_only=True)
    permisos = serializers.SerializerMethodField()

    class Meta:
        model = Rol
        fields = ['id_rol', 'nombre_rol', 'nombre_display', 'descripcion', 'permisos']

    def get_permisos(self, obj):
        """Devuelve solo los ID de permisos para que el frontend pueda marcarlos."""
        return list(
            obj.rol_permisos.select_related('id_permiso')
            .order_by('id_permiso__modulo', 'id_permiso__id_permiso')
            .values_list('id_permiso_id', flat=True)
        )


class PermisoSerializer(serializers.ModelSerializer):
    """Expone los permisos disponibles para administracion de roles."""

    class Meta:
        model = Permiso
        fields = ['id_permiso', 'codigo', 'nombre', 'descripcion', 'modulo']


class UsuarioGestionSerializer(serializers.ModelSerializer):
    """Crea y actualiza usuarios desde el modulo de gestion del propietario."""

    nombre = serializers.CharField(source='first_name')
    apellido = serializers.CharField(source='last_name', allow_blank=True, required=False)
    correo = serializers.EmailField(allow_blank=True, required=False)
    password = serializers.CharField(write_only=True, required=False, allow_blank=True, trim_whitespace=False)
    id_rol = serializers.PrimaryKeyRelatedField(queryset=Rol.objects.all())
    rol = serializers.CharField(source='id_rol.nombre_rol', read_only=True)
    rol_nombre = serializers.CharField(source='get_rol_display', read_only=True)

    class Meta:
        model = Usuario
        fields = [
            'id_usuario',
            'nombre',
            'apellido',
            'username',
            'correo',
            'id_rol',
            'rol',
            'rol_nombre',
            'estado',
            'password',
        ]

    def create(self, validated_data):
        """Crea usuario, sincroniza estado/correo y encripta la contrasena."""
        password = validated_data.pop('password', '')
        usuario = Usuario(**validated_data)
        usuario.email = usuario.correo
        usuario.is_active = usuario.estado
        if password:
            usuario.set_password(password)
        else:
            usuario.set_unusable_password()
        usuario.save()
        return usuario

    def update(self, instance, validated_data):
        """Actualiza datos del usuario y cambia password solo cuando se envia uno nuevo."""
        password = validated_data.pop('password', '')

        for field, value in validated_data.items():
            setattr(instance, field, value)

        instance.email = instance.correo
        instance.is_active = instance.estado
        if password:
            instance.set_password(password)
        instance.save()
        return instance


class CategoriaSerializer(serializers.ModelSerializer):
    """Serializa categorias usadas para clasificar insumos."""

    class Meta:
        model = Categoria
        fields = ['id_categoria', 'nombre_categoria', 'descripcion']


class UnidadMedidaSerializer(serializers.ModelSerializer):
    """Serializa unidades de medida para entradas, salidas y stock."""

    class Meta:
        model = UnidadMedida
        fields = ['id_unidad', 'nombre_unidad', 'abreviatura']


class FeriadoSerializer(serializers.ModelSerializer):
    """Serializa feriados y fechas comerciales sincronizadas para planificacion."""

    class Meta:
        model = Feriado
        fields = ['id_feriado', 'fecha', 'nombre', 'pais']


class InsumoSerializer(serializers.ModelSerializer):
    """Expone insumos con categoria, unidad y cantidad actual de stock."""

    categoria = serializers.CharField(source='id_categoria.nombre_categoria', read_only=True)
    unidad = serializers.CharField(source='id_unidad.nombre_unidad', read_only=True)
    unidad_abreviatura = serializers.CharField(source='id_unidad.abreviatura', read_only=True)
    cantidad_actual = serializers.DecimalField(
        source='stock.cantidad_actual',
        max_digits=10,
        decimal_places=3,
        read_only=True,
        default=0,
    )

    class Meta:
        model = Insumo
        fields = [
            'id_insumo',
            'nombre',
            'descripcion',
            'id_categoria',
            'categoria',
            'id_unidad',
            'unidad',
            'unidad_abreviatura',
            'stock_minimo',
            'estado',
            'cantidad_actual',
        ]

    def create(self, validated_data):
        """Al crear un insumo tambien asegura su registro de stock inicial."""
        insumo = super().create(validated_data)
        Stock.objects.get_or_create(id_insumo=insumo)
        return insumo


class DetalleEntradaSerializer(serializers.ModelSerializer):
    """Representa cada insumo comprado dentro de una entrada."""

    insumo = serializers.CharField(source='id_insumo.nombre', read_only=True)
    unidad = serializers.CharField(source='id_insumo.id_unidad.nombre_unidad', read_only=True)
    subtotal = serializers.SerializerMethodField()
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))
    costo_unitario = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0, required=False)

    class Meta:
        model = DetalleEntrada
        fields = [
            'id_detalle_entrada',
            'id_insumo',
            'insumo',
            'unidad',
            'cantidad',
            'costo_unitario',
            'subtotal',
        ]

    def get_subtotal(self, obj):
        """Calcula el costo por linea: cantidad por costo unitario."""
        return obj.cantidad * obj.costo_unitario


class MermaEntradaSerializer(serializers.Serializer):
    """Datos de perdida detectada al registrar una entrada."""

    id_insumo = serializers.PrimaryKeyRelatedField(queryset=Insumo.objects.filter(estado=True))
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))
    observacion = serializers.CharField(allow_blank=False, trim_whitespace=True)


class MovimientoSerializer(serializers.ModelSerializer):
    fecha_operacion = serializers.DateTimeField(required=False, write_only=True)

    def validate_fecha_operacion(self, value):
        if value > timezone.now() + timedelta(minutes=5):
            raise serializers.ValidationError('La fecha del movimiento no puede estar en el futuro.')
        return value


class EntradaSerializer(MovimientoSerializer):
    """Registra compras de insumos y actualiza automaticamente el stock."""

    usuario = serializers.CharField(source='id_usuario.username', read_only=True)
    detalles = DetalleEntradaSerializer(many=True)
    mermas = MermaEntradaSerializer(many=True, required=False, write_only=True)
    total_compra = serializers.SerializerMethodField()

    class Meta:
        model = Entrada
        fields = [
            'id_entrada',
            'id_operacion',
            'fecha_operacion',
            'fecha_entrada',
            'id_usuario',
            'usuario',
            'observacion',
            'detalles',
            'mermas',
            'total_compra',
        ]
        read_only_fields = ['id_entrada', 'fecha_entrada', 'id_usuario', 'usuario']

    def get_total_compra(self, obj):
        """Suma todos los subtotales de la entrada."""
        return sum((detalle.cantidad * detalle.costo_unitario for detalle in obj.detalles.all()), 0)

    def validate_detalles(self, value):
        """Evita guardar entradas vacias sin ningun insumo."""
        if not value:
            raise serializers.ValidationError('Debe registrar al menos un insumo.')
        return value

    def validate(self, attrs):
        """Valida que la merma declarada corresponda a los insumos recibidos."""
        attrs = super().validate(attrs)
        detalles = attrs.get('detalles', [])
        mermas = attrs.get('mermas') or []

        cantidades_recibidas = {}
        for detalle in detalles:
            insumo = detalle['id_insumo']
            cantidades_recibidas[insumo.pk] = cantidades_recibidas.get(insumo.pk, Decimal('0')) + detalle['cantidad']

        cantidades_merma = {}
        for merma in mermas:
            insumo = merma['id_insumo']
            if insumo.pk not in cantidades_recibidas:
                raise serializers.ValidationError('La merma debe corresponder a un insumo incluido en la entrada.')
            cantidades_merma[insumo.pk] = cantidades_merma.get(insumo.pk, Decimal('0')) + merma['cantidad']
            if cantidades_merma[insumo.pk] > cantidades_recibidas[insumo.pk]:
                raise serializers.ValidationError('La merma no puede superar la cantidad recibida del insumo.')

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Guarda la entrada completa y aumenta el stock de cada insumo."""
        detalles = validated_data.pop('detalles')
        mermas = validated_data.pop('mermas', [])
        fecha = validated_data.pop('fecha_operacion', timezone.now())
        entrada = Entrada.objects.create(
            fecha_entrada=fecha,
            id_usuario=self.context['request'].user,
            **validated_data,
        )

        for detalle_data in detalles:
            detalle = DetalleEntrada.objects.create(id_entrada=entrada, **detalle_data)
            stock, _ = Stock.objects.get_or_create(id_insumo=detalle.id_insumo)
            # Aqui se guarda la cantidad comprada: cada detalle de entrada suma al stock actual.
            stock.cantidad_actual += detalle.cantidad
            stock.save(update_fields=['cantidad_actual', 'fecha_actualizacion'])

        for merma_data in mermas:
            merma = Merma.objects.create(
                fecha_merma=fecha,
                id_usuario=self.context['request'].user,
                id_insumo=merma_data['id_insumo'],
                cantidad=merma_data['cantidad'],
                motivo='Recepción',
                observacion=merma_data['observacion'],
            )
            stock, _ = Stock.objects.get_or_create(id_insumo=merma.id_insumo)
            if merma.cantidad > stock.cantidad_actual:
                raise serializers.ValidationError('La merma no puede ser mayor al stock actual.')
            stock.cantidad_actual -= merma.cantidad
            stock.save(update_fields=['cantidad_actual', 'fecha_actualizacion'])
            evaluar_stock_insumo(merma.id_insumo)

        transaction.on_commit(lambda: enviar_movimiento_stock(entrada, 'entrada'), robust=True)
        return entrada


class DetalleSalidaSerializer(serializers.ModelSerializer):
    """Representa cada insumo consumido dentro de una salida."""

    insumo = serializers.CharField(source='id_insumo.nombre', read_only=True)
    unidad = serializers.CharField(source='id_insumo.id_unidad.nombre_unidad', read_only=True)
    cantidad = serializers.DecimalField(max_digits=10, decimal_places=3, min_value=Decimal('0.001'))

    class Meta:
        model = DetalleSalida
        fields = ['id_detalle_salida', 'id_insumo', 'insumo', 'unidad', 'cantidad']


class SalidaSerializer(MovimientoSerializer):
    """Registra salidas, valida disponibilidad y genera alertas de stock minimo."""

    usuario = serializers.CharField(source='id_usuario.username', read_only=True)
    detalles = DetalleSalidaSerializer(many=True)

    class Meta:
        model = Salida
        fields = [
            'id_salida',
            'id_operacion',
            'fecha_operacion',
            'fecha_salida',
            'id_usuario',
            'usuario',
            'motivo',
            'observacion',
            'plato',
            'tamano',
            'cantidad_platos',
            'precio_unitario',
            'total_venta_estimado',
            'detalles',
        ]
        read_only_fields = ['id_salida', 'fecha_salida', 'id_usuario', 'usuario']

    def validate_detalles(self, value):
        """Valida que exista stock suficiente antes de permitir el descuento."""
        if not value:
            raise serializers.ValidationError('Debe registrar al menos un insumo.')

        plato = self.initial_data.get('plato', '')
        tamano = self.initial_data.get('tamano', '')
        cantidades_por_insumo = {}
        for detalle in value:
            insumo = detalle['id_insumo']
            cantidades_por_insumo[insumo] = cantidades_por_insumo.get(insumo, 0) + detalle['cantidad']

        for insumo, cantidad_total in cantidades_por_insumo.items():
            valido, mensaje = validar_salida_respetando_minimo(
                {'id_insumo': insumo, 'cantidad': cantidad_total},
                plato=plato,
                tamano=tamano,
            )
            if not valido:
                raise serializers.ValidationError(mensaje)
        return value

    @transaction.atomic
    def create(self, validated_data):
        """Guarda la salida, descuenta stock y notifica cuando llega al minimo."""
        detalles = validated_data.pop('detalles')
        fecha = validated_data.pop('fecha_operacion', timezone.now())
        salida = Salida.objects.create(
            fecha_salida=fecha,
            id_usuario=self.context['request'].user,
            **validated_data,
        )

        for detalle_data in detalles:
            detalle = DetalleSalida.objects.create(id_salida=salida, **detalle_data)
            stock, _ = Stock.objects.get_or_create(id_insumo=detalle.id_insumo)
            # Aqui se descuenta el consumo: cada detalle de salida resta la cantidad usada del stock.
            stock.cantidad_actual -= detalle.cantidad
            stock.save(update_fields=['cantidad_actual', 'fecha_actualizacion'])

            evaluar_stock_insumo(
                detalle.id_insumo,
                stock.cantidad_actual,
                contexto=f'Plato: {salida.plato}. Tamano: {salida.tamano}.',
            )

        transaction.on_commit(lambda: enviar_movimiento_stock(salida, 'salida'), robust=True)
        return salida


class MermaSerializer(MovimientoSerializer):
    """Registra perdidas reales de insumos y descuenta stock sin contar venta."""

    usuario = serializers.CharField(source='id_usuario.username', read_only=True)
    insumo = serializers.CharField(source='id_insumo.nombre', read_only=True)
    unidad = serializers.CharField(source='id_insumo.id_unidad.nombre_unidad', read_only=True)

    class Meta:
        model = Merma
        fields = [
            'id_merma',
            'id_operacion',
            'fecha_operacion',
            'fecha_merma',
            'id_usuario',
            'usuario',
            'id_insumo',
            'insumo',
            'unidad',
            'cantidad',
            'motivo',
            'observacion',
        ]
        read_only_fields = ['id_merma', 'fecha_merma', 'id_usuario', 'usuario', 'insumo', 'unidad']

    def validate_cantidad(self, value):
        """Evita registrar mermas vacias o negativas."""
        if value <= 0:
            raise serializers.ValidationError('La cantidad de merma debe ser mayor a cero.')
        return value

    def validate_motivo(self, value):
        """Mantiene el registro de merma enfocado en recortes de produccion."""
        if value not in ['Recorte', 'Recepción']:
            raise serializers.ValidationError('El registro de merma solo permite los motivos Recorte o Recepción.')
        return value

    def validate(self, attrs):
        """La merma no puede superar el stock disponible del insumo."""
        insumo = attrs['id_insumo']
        stock, _ = Stock.objects.get_or_create(id_insumo=insumo)
        if attrs['cantidad'] > stock.cantidad_actual:
            raise serializers.ValidationError('La merma no puede ser mayor al stock actual.')
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """Guarda la merma y resta esa cantidad del stock actual."""
        fecha = validated_data.pop('fecha_operacion', timezone.now())
        merma = Merma.objects.create(
            fecha_merma=fecha,
            id_usuario=self.context['request'].user,
            **validated_data,
        )
        stock, _ = Stock.objects.get_or_create(id_insumo=merma.id_insumo)
        # Aqui se descuenta la merma: baja stock, pero no suma ventas ni platos vendidos.
        stock.cantidad_actual -= merma.cantidad
        stock.save(update_fields=['cantidad_actual', 'fecha_actualizacion'])
        evaluar_stock_insumo(merma.id_insumo)
        transaction.on_commit(lambda: enviar_movimiento_stock(merma, 'merma'), robust=True)
        return merma


class NotificacionSerializer(serializers.ModelSerializer):
    """Convierte alertas de stock o feriados para mostrarlas en la interfaz."""

    insumo = serializers.SerializerMethodField()
    unidad = serializers.SerializerMethodField()
    cantidad_actual = serializers.SerializerMethodField()
    feriado = serializers.CharField(source='id_feriado.nombre', read_only=True, default='')
    fecha_feriado = serializers.DateField(source='id_feriado.fecha', read_only=True)

    def get_insumo(self, obj):
        """Devuelve el nombre del insumo cuando la alerta pertenece al inventario."""
        return obj.id_insumo.nombre if obj.id_insumo else ''

    def get_unidad(self, obj):
        """Devuelve la unidad del insumo cuando existe una relacion con stock."""
        return obj.id_insumo.id_unidad.nombre_unidad if obj.id_insumo else ''

    def get_cantidad_actual(self, obj):
        """Devuelve el stock actual solo para alertas relacionadas con insumos."""
        if obj.id_insumo and hasattr(obj.id_insumo, 'stock'):
            return obj.id_insumo.stock.cantidad_actual
        return None

    class Meta:
        model = Notificacion
        fields = [
            'id_notificacion',
            'id_insumo',
            'id_feriado',
            'insumo',
            'unidad',
            'cantidad_actual',
            'feriado',
            'fecha_feriado',
            'mensaje',
            'fecha',
            'estado',
            'tipo',
        ]
