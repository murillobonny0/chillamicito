from django.db import migrations


PERMISOS = [
    ('iniciar_sesion', 'Iniciar sesion', 'Acceso', 'Permite ingresar al sistema.'),
    ('gestionar_usuarios', 'Gestionar usuarios', 'Usuarios', 'Crear, editar y desactivar usuarios.'),
    ('gestionar_roles_permisos', 'Gestionar roles y permisos', 'Usuarios', 'Modificar permisos asignados a roles.'),
    ('registrar_insumos', 'Registrar insumos', 'Insumos', 'Crear nuevos insumos.'),
    ('modificar_insumos', 'Modificar insumos', 'Insumos', 'Editar datos de insumos.'),
    ('consultar_stock', 'Consultar stock disponible', 'Stock', 'Ver cantidades actuales de insumos.'),
    ('registrar_entrada', 'Registrar entrada de insumos', 'Movimientos', 'Registrar ingresos al almacen.'),
    ('registrar_salida', 'Registrar salida de insumos', 'Movimientos', 'Registrar consumos o salidas.'),
    ('recibir_alertas_stock', 'Recibir alertas de stock minimo', 'Notificaciones', 'Ver alertas generadas por stock minimo.'),
    ('recibir_notificaciones_feriados', 'Recibir notificaciones de feriados', 'Notificaciones', 'Ver avisos de feriados para planificacion.'),
    ('consultar_reportes', 'Consultar reportes', 'Reportes', 'Acceder a reportes del sistema.'),
    ('visualizar_dashboards_bi', 'Visualizar dashboards BI', 'Reportes', 'Acceder a dashboards de Business Intelligence.'),
]

PERMISOS_POR_ROL = {
    'propietario': [codigo for codigo, _, _, _ in PERMISOS],
    'chef': ['iniciar_sesion', 'consultar_stock'],
    'ayudante_cocina': [
        'iniciar_sesion',
        'registrar_insumos',
        'modificar_insumos',
        'consultar_stock',
        'registrar_entrada',
        'registrar_salida',
    ],
}


def crear_permisos(apps, schema_editor):
    Rol = apps.get_model('usuarios', 'Rol')
    Permiso = apps.get_model('usuarios', 'Permiso')
    RolPermiso = apps.get_model('usuarios', 'RolPermiso')

    permisos_por_codigo = {}
    for codigo, nombre, modulo, descripcion in PERMISOS:
        permiso, _ = Permiso.objects.update_or_create(
            codigo=codigo,
            defaults={'nombre': nombre, 'modulo': modulo, 'descripcion': descripcion},
        )
        permisos_por_codigo[codigo] = permiso

    for nombre_rol, codigos in PERMISOS_POR_ROL.items():
        try:
            rol = Rol.objects.get(nombre_rol=nombre_rol)
        except Rol.DoesNotExist:
            continue

        for codigo in codigos:
            RolPermiso.objects.get_or_create(
                id_rol=rol,
                id_permiso=permisos_por_codigo[codigo],
            )


def eliminar_permisos(apps, schema_editor):
    Permiso = apps.get_model('usuarios', 'Permiso')
    Permiso.objects.filter(codigo__in=[codigo for codigo, _, _, _ in PERMISOS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('usuarios', '0003_permiso_rolpermiso'),
    ]

    operations = [
        migrations.RunPython(crear_permisos, eliminar_permisos),
    ]
