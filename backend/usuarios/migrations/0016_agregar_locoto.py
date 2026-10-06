from decimal import Decimal

from django.db import migrations


def agregar_locoto(apps, schema_editor):
    Categoria = apps.get_model('usuarios', 'Categoria')
    UnidadMedida = apps.get_model('usuarios', 'UnidadMedida')
    Insumo = apps.get_model('usuarios', 'Insumo')
    Stock = apps.get_model('usuarios', 'Stock')

    categoria, _ = Categoria.objects.update_or_create(
        nombre_categoria='Verduras',
        defaults={'descripcion': 'Verduras utilizadas en la preparacion diaria.'},
    )
    unidad, _ = UnidadMedida.objects.update_or_create(
        nombre_unidad='Kilo',
        defaults={'abreviatura': 'kg'},
    )

    locoto = Insumo.objects.filter(nombre__iexact='Locoto').first()
    datos = {
        'descripcion': (
            'Verdura picante utilizada como complemento del pique; '
            'se compra por arroba y se controla en kilos. '
            'Una arroba equivale a 11 kg.'
        ),
        'id_categoria': categoria,
        'id_unidad': unidad,
        'stock_minimo': Decimal('2.000'),
        'estado': True,
    }

    if locoto:
        for field, value in datos.items():
            setattr(locoto, field, value)
        locoto.nombre = 'Locoto'
        locoto.save()
    else:
        locoto = Insumo.objects.create(nombre='Locoto', **datos)

    Stock.objects.get_or_create(id_insumo=locoto)


def quitar_locoto(apps, schema_editor):
    Insumo = apps.get_model('usuarios', 'Insumo')
    Insumo.objects.filter(nombre__iexact='Locoto').update(estado=False)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0015_alter_hechomovimientostock_origen_merma'),
    ]

    operations = [
        migrations.RunPython(agregar_locoto, quitar_locoto),
    ]
