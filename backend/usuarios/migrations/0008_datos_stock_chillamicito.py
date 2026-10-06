from decimal import Decimal

from django.db import migrations


def get_or_update(model, lookup_field, lookup_value, defaults):
    obj = model.objects.filter(**{f'{lookup_field}__iexact': lookup_value}).first()
    if obj:
        for field, value in defaults.items():
            setattr(obj, field, value)
        setattr(obj, lookup_field, lookup_value)
        obj.save()
        return obj

    return model.objects.create(**{lookup_field: lookup_value}, **defaults)


def cargar_datos_stock(apps, schema_editor):
    Categoria = apps.get_model('usuarios', 'Categoria')
    UnidadMedida = apps.get_model('usuarios', 'UnidadMedida')
    Insumo = apps.get_model('usuarios', 'Insumo')
    Stock = apps.get_model('usuarios', 'Stock')

    categorias = {
        'Carnes': 'Carnes utilizadas segun el tipo de plato.',
        'Papa': 'Papa recibida por carga; para stock se controla en kilos.',
        'Verduras': 'Verduras utilizadas en la preparacion diaria.',
        'Pescados': 'Insumos de pescado, principalmente surubi.',
    }
    categorias_db = {
        nombre: get_or_update(Categoria, 'nombre_categoria', nombre, {'descripcion': descripcion})
        for nombre, descripcion in categorias.items()
    }

    unidades = {
        'Kilo': 'kg',
        'Unidad': 'u',
        'Carga': 'carga',
    }
    unidades_db = {
        nombre: get_or_update(UnidadMedida, 'nombre_unidad', nombre, {'abreviatura': abreviatura})
        for nombre, abreviatura in unidades.items()
    }

    insumos = [
        {
            'nombre': 'Carne',
            'categoria': 'Carnes',
            'unidad': 'Kilo',
            'stock_minimo': Decimal('60.000'),
            'descripcion': (
                'Stock minimo semanal de carne. Tipos: Chillami usa lapping; '
                'Macho y Borracho usan tortuguita; Brasa usa lomo.'
            ),
        },
        {
            'nombre': 'Papa',
            'categoria': 'Papa',
            'unidad': 'Kilo',
            'stock_minimo': Decimal('150.000'),
            'descripcion': 'Stock minimo de 1.5 cargas; una carga equivale aproximadamente a 100 kg.',
        },
        {
            'nombre': 'Chorizo normal',
            'categoria': 'Carnes',
            'unidad': 'Kilo',
            'stock_minimo': Decimal('13.000'),
            'descripcion': 'Chorizo normal utilizado en preparaciones principales.',
        },
        {
            'nombre': 'Chorizo parrillero',
            'categoria': 'Carnes',
            'unidad': 'Kilo',
            'stock_minimo': Decimal('13.000'),
            'descripcion': 'Chorizo parrillero utilizado para el Pique a la Brasa.',
        },
        {
            'nombre': 'Tomate',
            'categoria': 'Verduras',
            'unidad': 'Kilo',
            'stock_minimo': Decimal('6.000'),
            'descripcion': 'Verdura con pedido semanal; el precio suele subir en invierno.',
        },
        {
            'nombre': 'Cebolla',
            'categoria': 'Verduras',
            'unidad': 'Kilo',
            'stock_minimo': Decimal('6.000'),
            'descripcion': 'Verdura con pedido semanal; el precio suele subir en invierno.',
        },
        {
            'nombre': 'Surubi',
            'categoria': 'Pescados',
            'unidad': 'Kilo',
            'stock_minimo': Decimal('6.000'),
            'descripcion': 'Insumo principal para el plato de Surubi.',
        },
    ]

    for item in insumos:
        insumo = Insumo.objects.filter(nombre__iexact=item['nombre']).first()
        if not insumo and item['nombre'] == 'Chorizo normal':
            insumo = Insumo.objects.filter(nombre__iexact='Chorizo').first()

        datos = {
            'descripcion': item['descripcion'],
            'id_categoria': categorias_db[item['categoria']],
            'id_unidad': unidades_db[item['unidad']],
            'stock_minimo': item['stock_minimo'],
            'estado': True,
        }

        if insumo:
            for field, value in datos.items():
                setattr(insumo, field, value)
            insumo.nombre = item['nombre']
            insumo.save()
        else:
            insumo = Insumo.objects.create(nombre=item['nombre'], **datos)

        Stock.objects.get_or_create(id_insumo=insumo)


def revertir_datos_stock(apps, schema_editor):
    Insumo = apps.get_model('usuarios', 'Insumo')
    Insumo.objects.filter(
        nombre__in=[
            'Chorizo normal',
            'Chorizo parrillero',
            'Surubi',
        ]
    ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0007_notificacion_tipo_alter_detalleentrada_cantidad_and_more'),
    ]

    operations = [
        migrations.RunPython(cargar_datos_stock, revertir_datos_stock),
    ]
