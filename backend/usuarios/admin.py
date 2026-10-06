from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import (
    Categoria,
    DetalleEntrada,
    DetalleSalida,
    DimCategoria,
    DimInsumo,
    DimTiempo,
    DimTipoMovimiento,
    DimUsuario,
    Entrada,
    Feriado,
    HechoMovimientoStock,
    Insumo,
    Notificacion,
    Permiso,
    RegistroETL,
    Rol,
    RolPermiso,
    Salida,
    Stock,
    UnidadMedida,
    Usuario,
)


@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    """Configura como se visualizan los roles en el panel admin de Django."""

    list_display = ('id_rol', 'nombre_rol', 'descripcion')
    search_fields = ('nombre_rol',)


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """Admin de Django Auth mostrando el rol usado por la interfaz React."""

    fieldsets = UserAdmin.fieldsets + (
        ('Rol del restaurante', {'fields': ('id_rol', 'correo', 'estado')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Rol del restaurante', {'fields': ('id_rol', 'correo', 'estado')}),
    )
    list_display = ('username', 'first_name', 'last_name', 'id_rol', 'estado', 'is_staff')
    list_filter = ('id_rol', 'estado', 'is_staff', 'is_superuser')


# Registro de modelos para poder inspeccionar datos desde /admin durante pruebas.
admin.site.register(Categoria)
admin.site.register(Permiso)
admin.site.register(RolPermiso)
admin.site.register(UnidadMedida)
admin.site.register(Insumo)
admin.site.register(Entrada)
admin.site.register(DetalleEntrada)
admin.site.register(Salida)
admin.site.register(DetalleSalida)
admin.site.register(Stock)
admin.site.register(Notificacion)
admin.site.register(Feriado)
admin.site.register(RegistroETL)
admin.site.register(DimCategoria)
admin.site.register(DimInsumo)
admin.site.register(DimTiempo)
admin.site.register(DimUsuario)
admin.site.register(DimTipoMovimiento)
admin.site.register(HechoMovimientoStock)
