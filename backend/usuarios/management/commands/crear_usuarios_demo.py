from django.core.management.base import BaseCommand

from usuarios.models import Rol, Usuario


class Command(BaseCommand):
    """Comando auxiliar para cargar usuarios demo con sus roles."""

    help = 'Crea usuarios para probar login y roles del sistema.'

    def handle(self, *args, **options):
        """Crea o actualiza roles y usuarios base usados en pruebas."""
        roles = {
            Rol.Nombre.PROPIETARIO: Rol.objects.get_or_create(
                nombre_rol=Rol.Nombre.PROPIETARIO,
                defaults={'descripcion': 'Acceso total al sistema.'},
            )[0],
            Rol.Nombre.CHEF: Rol.objects.get_or_create(
                nombre_rol=Rol.Nombre.CHEF,
                defaults={'descripcion': 'Consulta disponibilidad de insumos.'},
            )[0],
            Rol.Nombre.AYUDANTE_COCINA: Rol.objects.get_or_create(
                nombre_rol=Rol.Nombre.AYUDANTE_COCINA,
                defaults={'descripcion': 'Registra entradas y salidas de insumos.'},
            )[0],
        }

        usuarios = [
            {
                'username': 'Bonny',
                'password': 'bonny22',
                'first_name': 'Bonny',
                'last_name': 'Propietario',
                'id_rol': roles[Rol.Nombre.PROPIETARIO],
                'is_staff': True,
                'is_superuser': True,
            },
            {
                'username': 'juan',
                'password': 'juan11',
                'first_name': 'juan',
                'last_name': 'Chef',
                'id_rol': roles[Rol.Nombre.CHEF],
            },
            {
                'username': 'Maria',
                'password': 'maria33',
                'first_name': 'Maria',
                'last_name': 'Ayudante',
                'id_rol': roles[Rol.Nombre.AYUDANTE_COCINA],
            },
        ]

        for data in usuarios:
            password = data.pop('password')
            # get_or_create evita duplicar usuarios si el comando se ejecuta varias veces.
            usuario, created = Usuario.objects.get_or_create(
                username=data['username'],
                defaults=data,
            )

            if created:
                # set_password guarda la contrasena con hash de Django Auth.
                usuario.set_password(password)
                usuario.save()
                self.stdout.write(self.style.SUCCESS(f'Creado: {usuario.username}'))
            else:
                for field, value in data.items():
                    setattr(usuario, field, value)
                usuario.set_password(password)
                usuario.estado = True
                usuario.is_active = True
                usuario.save()
                self.stdout.write(self.style.SUCCESS(f'Actualizado: {usuario.username}'))
