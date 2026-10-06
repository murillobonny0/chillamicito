from django.db import migrations


def crear_datos_iniciales(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    DimTipoMovimiento = apps.get_model('usuarios', 'DimTipoMovimiento')

    roles = [
        ('propietario', 'Acceso total a usuarios, stock, alertas, reportes y dashboards.'),
        ('chef', 'Consulta stock y disponibilidad de insumos.'),
        ('ayudante_cocina', 'Registra insumos, entradas, salidas y consulta stock.'),
    ]
    for nombre_rol, descripcion in roles:
        Rol.objects.get_or_create(
            nombre_rol=nombre_rol,
            defaults={'descripcion': descripcion},
        )

    tipos_movimiento = [
        ('entrada', 'Ingreso de insumos al almacen.'),
        ('salida', 'Salida de insumos del almacen.'),
        ('consumo', 'Consumo registrado para preparacion.'),
        ('ajuste', 'Correccion manual de stock.'),
    ]
    for nombre, descripcion in tipos_movimiento:
        DimTipoMovimiento.objects.get_or_create(
            nombre=nombre,
            defaults={'descripcion': descripcion},
        )


def eliminar_datos_iniciales(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    DimTipoMovimiento = apps.get_model('usuarios', 'DimTipoMovimiento')
    Rol.objects.filter(nombre_rol__in=['propietario', 'chef', 'ayudante_cocina']).delete()
    DimTipoMovimiento.objects.filter(nombre__in=['entrada', 'salida', 'consumo', 'ajuste']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_datos_iniciales, eliminar_datos_iniciales),
    ]
