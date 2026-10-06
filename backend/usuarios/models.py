from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


# Define los roles principales del sistema y permite controlar accesos por perfil.
class Rol(models.Model):
    class Nombre(models.TextChoices):
        PROPIETARIO = 'propietario', 'Propietario'
        CHEF = 'chef', 'Chef'
        AYUDANTE_COCINA = 'ayudante_cocina', 'Ayudante de cocina'

    id_rol = models.AutoField(primary_key=True)
    nombre_rol = models.CharField(max_length=50, choices=Nombre.choices, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'rol'
        verbose_name = 'rol'
        verbose_name_plural = 'roles'

    def __str__(self):
        return self.get_nombre_rol_display()


# Representa una accion permitida dentro del sistema, agrupada por modulo funcional.
class Permiso(models.Model):
    id_permiso = models.AutoField(primary_key=True)
    codigo = models.CharField(max_length=60, unique=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    modulo = models.CharField(max_length=80)

    class Meta:
        db_table = 'permiso'
        ordering = ['modulo', 'id_permiso']

    def __str__(self):
        return self.nombre


# Tabla intermedia que relaciona cada rol con los permisos que puede ejecutar.
class RolPermiso(models.Model):
    id_rol_permiso = models.AutoField(primary_key=True)
    id_rol = models.ForeignKey(
        Rol,
        on_delete=models.CASCADE,
        db_column='id_rol',
        related_name='rol_permisos',
    )
    id_permiso = models.ForeignKey(
        Permiso,
        on_delete=models.CASCADE,
        db_column='id_permiso',
        related_name='rol_permisos',
    )

    class Meta:
        db_table = 'rol_permiso'
        constraints = [
            models.UniqueConstraint(fields=['id_rol', 'id_permiso'], name='uq_rol_permiso'),
        ]

    def __str__(self):
        return f'{self.id_rol} - {self.id_permiso}'


# Usuario personalizado de Django; agrega rol, correo y estado activo/inactivo.
class Usuario(AbstractUser):
    id_usuario = models.AutoField(primary_key=True)
    id_rol = models.ForeignKey(
        Rol,
        on_delete=models.PROTECT,
        db_column='id_rol',
        related_name='usuarios',
    )
    correo = models.EmailField(blank=True)
    estado = models.BooleanField(default=True)

    REQUIRED_FIELDS = ['id_rol']

    class Meta:
        db_table = 'usuario'

    @property
    def nombre(self):
        return self.first_name

    @property
    def apellido(self):
        return self.last_name

    @property
    def rol(self):
        return self.id_rol.nombre_rol

    def get_rol_display(self):
        return self.id_rol.get_nombre_rol_display()

    def __str__(self):
        return f'{self.username} ({self.get_rol_display()})'


# Agrupa los insumos por tipo para consultas, reportes y dashboards.
class Categoria(models.Model):
    id_categoria = models.AutoField(primary_key=True)
    nombre_categoria = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'categoria'
        verbose_name = 'categoria'
        verbose_name_plural = 'categorias'

    def __str__(self):
        return self.nombre_categoria


# Define la unidad en la que se mide cada insumo: kilo, unidad, caja, etc.
class UnidadMedida(models.Model):
    id_unidad = models.AutoField(primary_key=True)
    nombre_unidad = models.CharField(max_length=80, unique=True)
    abreviatura = models.CharField(max_length=20, blank=True)

    class Meta:
        db_table = 'unidad_medida'
        verbose_name = 'unidad de medida'
        verbose_name_plural = 'unidades de medida'

    def __str__(self):
        return self.abreviatura or self.nombre_unidad


# Producto o materia prima que se controla dentro del inventario del restaurante.
class Insumo(models.Model):
    id_insumo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    id_categoria = models.ForeignKey(
        Categoria,
        on_delete=models.PROTECT,
        db_column='id_categoria',
        related_name='insumos',
    )
    id_unidad = models.ForeignKey(
        UnidadMedida,
        on_delete=models.PROTECT,
        db_column='id_unidad',
        related_name='insumos',
    )
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    estado = models.BooleanField(default=True)

    class Meta:
        db_table = 'insumo'
        constraints = [
            models.UniqueConstraint(
                fields=['nombre', 'id_categoria', 'id_unidad'],
                name='uq_insumo_nombre_categoria_unidad',
            ),
        ]

    def __str__(self):
        return self.nombre


# Cabecera de una compra o ingreso de insumos al almacen.
class Entrada(models.Model):
    id_entrada = models.AutoField(primary_key=True)
    # Identificador enviado por el cliente para no duplicar sincronizaciones offline.
    id_operacion = models.CharField(max_length=64, unique=True, null=True, blank=True)
    fecha_entrada = models.DateTimeField(default=timezone.now)
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        db_column='id_usuario',
        related_name='entradas',
    )
    observacion = models.TextField(blank=True)

    class Meta:
        db_table = 'entrada'

    def __str__(self):
        return f'Entrada {self.id_entrada}'


# Detalle de cada insumo comprado dentro de una entrada.
class DetalleEntrada(models.Model):
    id_detalle_entrada = models.AutoField(primary_key=True)
    id_entrada = models.ForeignKey(
        Entrada,
        on_delete=models.CASCADE,
        db_column='id_entrada',
        related_name='detalles',
    )
    id_insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        db_column='id_insumo',
        related_name='detalles_entrada',
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'detalle_entrada'

    def __str__(self):
        return f'{self.id_insumo} x {self.cantidad}'


# Cabecera de una salida de insumos por preparacion o consumo de platos.
class Salida(models.Model):
    class Tamano(models.TextChoices):
        MEDIO = 'medio', 'Medio'
        ENTERO = 'entero', 'Entero'

    id_salida = models.AutoField(primary_key=True)
    # Identificador enviado por el cliente para no duplicar sincronizaciones offline.
    id_operacion = models.CharField(max_length=64, unique=True, null=True, blank=True)
    fecha_salida = models.DateTimeField(default=timezone.now)
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        db_column='id_usuario',
        related_name='salidas',
    )
    motivo = models.CharField(max_length=120, blank=True)
    observacion = models.TextField(blank=True)
    plato = models.CharField(max_length=80, blank=True)
    tamano = models.CharField(max_length=20, choices=Tamano.choices, blank=True)
    cantidad_platos = models.PositiveIntegerField(default=0)
    precio_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_venta_estimado = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'salida'

    def __str__(self):
        return f'Salida {self.id_salida}'


# Detalle de cada insumo descontado dentro de una salida.
class DetalleSalida(models.Model):
    id_detalle_salida = models.AutoField(primary_key=True)
    id_salida = models.ForeignKey(
        Salida,
        on_delete=models.CASCADE,
        db_column='id_salida',
        related_name='detalles',
    )
    id_insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        db_column='id_insumo',
        related_name='detalles_salida',
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)

    class Meta:
        db_table = 'detalle_salida'

    def __str__(self):
        return f'{self.id_insumo} x {self.cantidad}'


# Registra perdida real de insumo; no representa venta ni plato preparado.
class Merma(models.Model):
    id_merma = models.AutoField(primary_key=True)
    # Identificador enviado por el cliente para no duplicar sincronizaciones offline.
    id_operacion = models.CharField(max_length=64, unique=True, null=True, blank=True)
    fecha_merma = models.DateTimeField(default=timezone.now)
    id_usuario = models.ForeignKey(
        Usuario,
        on_delete=models.PROTECT,
        db_column='id_usuario',
        related_name='mermas',
    )
    id_insumo = models.ForeignKey(
        Insumo,
        on_delete=models.PROTECT,
        db_column='id_insumo',
        related_name='mermas',
    )
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    motivo = models.CharField(max_length=120)
    observacion = models.TextField(blank=True)

    class Meta:
        db_table = 'merma'

    def __str__(self):
        return f'Merma {self.id_merma} - {self.id_insumo}'


# Mantiene la cantidad actual disponible de cada insumo.
class Stock(models.Model):
    id_stock = models.AutoField(primary_key=True)
    id_insumo = models.OneToOneField(
        Insumo,
        on_delete=models.CASCADE,
        db_column='id_insumo',
        related_name='stock',
    )
    cantidad_actual = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    fecha_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock'

    def __str__(self):
        return f'{self.id_insumo}: {self.cantidad_actual}'


# Guarda alertas internas del sistema: stock minimo, insuficiente o feriados proximos.
class Notificacion(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        LEIDA = 'leida', 'Leida'

    class Tipo(models.TextChoices):
        STOCK_MINIMO = 'stock_minimo', 'Stock minimo'
        STOCK_PREVENTIVO = 'stock_preventivo', 'Stock preventivo'
        AGOTADO = 'agotado', 'Producto agotado'
        STOCK_INSUFICIENTE = 'stock_insuficiente', 'Stock insuficiente'
        FERIADO = 'feriado', 'Feriado'

    id_notificacion = models.AutoField(primary_key=True)
    id_insumo = models.ForeignKey(
        Insumo,
        on_delete=models.CASCADE,
        db_column='id_insumo',
        related_name='notificaciones',
        null=True,
        blank=True,
    )
    id_feriado = models.ForeignKey(
        'Feriado',
        on_delete=models.CASCADE,
        db_column='id_feriado',
        related_name='notificaciones',
        null=True,
        blank=True,
    )
    mensaje = models.TextField()
    fecha = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    tipo = models.CharField(max_length=30, choices=Tipo.choices, default=Tipo.STOCK_MINIMO)

    class Meta:
        db_table = 'notificacion'

    def __str__(self):
        return self.mensaje[:80]


# Almacena feriados y fechas comerciales sincronizadas desde Nager.Date y datos locales.
class Feriado(models.Model):
    id_feriado = models.AutoField(primary_key=True)
    fecha = models.DateField()
    nombre = models.CharField(max_length=150)
    pais = models.CharField(max_length=2, default='BO')

    class Meta:
        db_table = 'feriado'
        constraints = [
            models.UniqueConstraint(fields=['fecha', 'pais'], name='uq_feriado_fecha_pais'),
        ]

    def __str__(self):
        return f'{self.fecha} - {self.nombre}'


# Registra cada ejecucion del proceso ETL para saber si el Data Mart fue cargado.
class RegistroETL(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        EJECUTADO = 'ejecutado', 'Ejecutado'
        ERROR = 'error', 'Error'

    id_etl = models.AutoField(primary_key=True)
    fecha_ejecucion = models.DateTimeField(default=timezone.now)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'registro_etl'

    def __str__(self):
        return f'ETL {self.id_etl} - {self.estado}'


# Dimension del Data Mart que guarda la categoria historica del insumo.
class DimCategoria(models.Model):
    id_dim_categoria = models.AutoField(primary_key=True)
    nombre_categoria = models.CharField(max_length=100)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'dim_categoria'

    def __str__(self):
        return self.nombre_categoria


# Dimension del Data Mart que guarda datos descriptivos del insumo.
class DimInsumo(models.Model):
    id_dim_insumo = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120)
    descripcion = models.TextField(blank=True)
    categoria = models.CharField(max_length=100, blank=True)
    unidad_medida = models.CharField(max_length=80, blank=True)
    stock_minimo = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    estado = models.BooleanField(default=True)

    class Meta:
        db_table = 'dim_insumo'

    def __str__(self):
        return self.nombre


# Dimension temporal usada por Power BI para analizar por calendario, hora y franja.
class DimTiempo(models.Model):
    id_dim_tiempo = models.AutoField(primary_key=True)
    fecha = models.DateField()
    dia = models.PositiveSmallIntegerField()
    mes = models.PositiveSmallIntegerField()
    nombre_mes = models.CharField(max_length=20, blank=True)
    trimestre = models.PositiveSmallIntegerField()
    anio = models.PositiveSmallIntegerField()
    hora = models.PositiveSmallIntegerField(default=0)
    franja_horaria = models.CharField(max_length=20, blank=True)
    dia_semana = models.PositiveSmallIntegerField(default=0)
    nombre_dia = models.CharField(max_length=20, blank=True)
    nivel_demanda = models.CharField(max_length=20, blank=True)
    motivo_demanda = models.CharField(max_length=180, blank=True)

    class Meta:
        db_table = 'dim_tiempo'
        constraints = [
            models.UniqueConstraint(fields=['fecha', 'hora'], name='uq_dim_tiempo_fecha_hora'),
        ]

    def __str__(self):
        return f'{self.fecha} {self.hora}:00'


# Dimension del usuario que realizo entradas o salidas de stock.
class DimUsuario(models.Model):
    id_dim_usuario = models.AutoField(primary_key=True)
    username = models.CharField(max_length=150)
    nombre = models.CharField(max_length=150, blank=True)
    apellido = models.CharField(max_length=150, blank=True)
    rol = models.CharField(max_length=50, blank=True)

    class Meta:
        db_table = 'dim_usuario'

    def __str__(self):
        return self.username


# Dimension que clasifica el movimiento como Entrada o Salida.
class DimTipoMovimiento(models.Model):
    id_dim_tipo_movimiento = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=50, unique=True)
    descripcion = models.TextField(blank=True)

    class Meta:
        db_table = 'dim_tipo_movimiento'

    def __str__(self):
        return self.nombre


# Tabla de hechos central del Data Mart: concentra cantidades, costos, ventas y stock.
class HechoMovimientoStock(models.Model):
    class Origen(models.TextChoices):
        ENTRADA = 'entrada', 'Entrada'
        SALIDA = 'salida', 'Salida'
        MERMA = 'merma', 'Merma'

    id_hecho_movimiento_stock = models.AutoField(primary_key=True)
    id_dim_insumo = models.ForeignKey(
        DimInsumo,
        on_delete=models.PROTECT,
        db_column='id_dim_insumo',
        related_name='hechos_movimiento',
    )
    id_dim_categoria = models.ForeignKey(
        DimCategoria,
        on_delete=models.PROTECT,
        db_column='id_dim_categoria',
        related_name='hechos_movimiento',
    )
    id_dim_tiempo = models.ForeignKey(
        DimTiempo,
        on_delete=models.PROTECT,
        db_column='id_dim_tiempo',
        related_name='hechos_movimiento',
    )
    id_dim_usuario = models.ForeignKey(
        DimUsuario,
        on_delete=models.PROTECT,
        db_column='id_dim_usuario',
        related_name='hechos_movimiento',
    )
    id_dim_tipo_movimiento = models.ForeignKey(
        DimTipoMovimiento,
        on_delete=models.PROTECT,
        db_column='id_dim_tipo_movimiento',
        related_name='hechos_movimiento',
    )
    origen = models.CharField(max_length=20, choices=Origen.choices, default=Origen.ENTRADA)
    id_origen_detalle = models.PositiveIntegerField(default=0)
    cantidad = models.DecimalField(max_digits=10, decimal_places=3)
    costo_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    stock_resultante = models.DecimalField(max_digits=10, decimal_places=3, default=0)
    estado_stock = models.CharField(max_length=20, blank=True)
    recomendacion_compra = models.CharField(max_length=80, blank=True)
    plato = models.CharField(max_length=80, blank=True)
    tamano = models.CharField(max_length=20, blank=True)
    cantidad_platos = models.PositiveIntegerField(default=0)
    venta_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    class Meta:
        db_table = 'hecho_movimiento_stock'
        constraints = [
            models.UniqueConstraint(fields=['origen', 'id_origen_detalle'], name='uq_hecho_origen_detalle'),
        ]

    def __str__(self):
        return f'Movimiento {self.id_hecho_movimiento_stock}'
