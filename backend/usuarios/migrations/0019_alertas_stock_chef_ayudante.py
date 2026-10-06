from django.db import migrations


def asignar_alertas_stock(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Permiso = apps.get_model('usuarios', 'Permiso')
    RolPermiso = apps.get_model('usuarios', 'RolPermiso')

    permiso = Permiso.objects.filter(codigo='recibir_alertas_stock').first()
    if not permiso:
        return

    for nombre_rol in ['chef', 'ayudante_cocina']:
        rol = Rol.objects.filter(nombre_rol=nombre_rol).first()
        if rol:
            RolPermiso.objects.get_or_create(id_rol=rol, id_permiso=permiso)


def quitar_alertas_stock(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Permiso = apps.get_model('usuarios', 'Permiso')
    RolPermiso = apps.get_model('usuarios', 'RolPermiso')

    permiso = Permiso.objects.filter(codigo='recibir_alertas_stock').first()
    if not permiso:
        return

    roles = Rol.objects.filter(nombre_rol__in=['chef', 'ayudante_cocina'])
    RolPermiso.objects.filter(id_rol__in=roles, id_permiso=permiso).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0018_entrada_id_operacion_merma_id_operacion_and_more'),
    ]

    operations = [
        migrations.RunPython(asignar_alertas_stock, quitar_alertas_stock),
    ]
