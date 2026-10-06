from django.db import migrations


def crear_catalogos_stock(apps, schema_editor):
    Categoria = apps.get_model('usuarios', 'Categoria')
    UnidadMedida = apps.get_model('usuarios', 'UnidadMedida')

    categorias = [
        ('Carnes', 'Insumos de origen carnico.'),
        ('Verduras', 'Productos vegetales utilizados en cocina.'),
        ('Papa', 'Insumo de papa utilizado en cocina.'),
    ]
    for nombre_categoria, descripcion in categorias:
        Categoria.objects.get_or_create(
            nombre_categoria=nombre_categoria,
            defaults={'descripcion': descripcion},
        )

    unidades = [
        ('Kilo', 'kg'),
        ('Unidad', 'u'),
        ('Carga', 'carga'),
    ]
    for nombre_unidad, abreviatura in unidades:
        UnidadMedida.objects.get_or_create(
            nombre_unidad=nombre_unidad,
            defaults={'abreviatura': abreviatura},
        )


def eliminar_catalogos_stock(apps, schema_editor):
    Categoria = apps.get_model('usuarios', 'Categoria')
    UnidadMedida = apps.get_model('usuarios', 'UnidadMedida')

    Categoria.objects.filter(nombre_categoria__in=['Carnes', 'Verduras', 'Papa']).delete()
    UnidadMedida.objects.filter(nombre_unidad__in=['Kilo', 'Unidad', 'Carga']).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0004_permisos_iniciales'),
    ]

    operations = [
        migrations.RunPython(crear_catalogos_stock, eliminar_catalogos_stock),
    ]
