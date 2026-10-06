from django.db import migrations


PERMISOS_OPERATIVOS_STOCK = [
    'registrar_insumos',
    'modificar_insumos',
    'registrar_entrada',
    'registrar_salida',
]

PERMISOS_PROPIETARIO = [
    'iniciar_sesion',
    'gestionar_usuarios',
    'gestionar_roles_permisos',
    'consultar_stock',
    'recibir_alertas_stock',
    'recibir_notificaciones_feriados',
    'consultar_reportes',
    'visualizar_dashboards_bi',
]

PERMISOS_AYUDANTE = [
    'iniciar_sesion',
    'registrar_insumos',
    'modificar_insumos',
    'consultar_stock',
    'registrar_entrada',
    'registrar_salida',
]


def ajustar_permisos(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Permiso = apps.get_model('usuarios', 'Permiso')
    RolPermiso = apps.get_model('usuarios', 'RolPermiso')

    try:
        propietario = Rol.objects.get(nombre_rol='propietario')
    except Rol.DoesNotExist:
        propietario = None

    if propietario:
        RolPermiso.objects.filter(
            id_rol=propietario,
            id_permiso__codigo__in=PERMISOS_OPERATIVOS_STOCK,
        ).delete()

        for codigo in PERMISOS_PROPIETARIO:
            permiso = Permiso.objects.filter(codigo=codigo).first()
            if permiso:
                RolPermiso.objects.get_or_create(id_rol=propietario, id_permiso=permiso)

    ayudante = Rol.objects.filter(nombre_rol='ayudante_cocina').first()
    if ayudante:
        for codigo in PERMISOS_AYUDANTE:
            permiso = Permiso.objects.filter(codigo=codigo).first()
            if permiso:
                RolPermiso.objects.get_or_create(id_rol=ayudante, id_permiso=permiso)


def revertir_permisos(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Permiso = apps.get_model('usuarios', 'Permiso')
    RolPermiso = apps.get_model('usuarios', 'RolPermiso')

    propietario = Rol.objects.filter(nombre_rol='propietario').first()
    if propietario:
        for permiso in Permiso.objects.filter(codigo__in=PERMISOS_OPERATIVOS_STOCK):
            RolPermiso.objects.get_or_create(id_rol=propietario, id_permiso=permiso)


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0016_agregar_locoto'),
    ]

    operations = [
        migrations.RunPython(ajustar_permisos, revertir_permisos),
    ]
