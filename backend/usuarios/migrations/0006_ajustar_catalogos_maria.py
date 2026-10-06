from django.db import migrations


def ajustar_catalogos(apps, schema_editor):
    Categoria = apps.get_model('usuarios', 'Categoria')
    UnidadMedida = apps.get_model('usuarios', 'UnidadMedida')

    Categoria.objects.filter(nombre_categoria='Tuberculos').update(
        nombre_categoria='Papa',
        descripcion='Insumo de papa utilizado en cocina.',
    )
    Categoria.objects.get_or_create(
        nombre_categoria='Papa',
        defaults={'descripcion': 'Insumo de papa utilizado en cocina.'},
    )
    UnidadMedida.objects.get_or_create(
        nombre_unidad='Carga',
        defaults={'abreviatura': 'carga'},
    )


def revertir_catalogos(apps, schema_editor):
    Categoria = apps.get_model('usuarios', 'Categoria')
    UnidadMedida = apps.get_model('usuarios', 'UnidadMedida')

    Categoria.objects.filter(nombre_categoria='Papa').update(
        nombre_categoria='Tuberculos',
        descripcion='Productos como papa y similares.',
    )
    UnidadMedida.objects.filter(nombre_unidad='Carga').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0005_catalogos_stock_base'),
    ]

    operations = [
        migrations.RunPython(ajustar_catalogos, revertir_catalogos),
    ]
