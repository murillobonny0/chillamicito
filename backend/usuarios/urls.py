from django.urls import path

from .views import (
    BIDashboardView,
    CatalogoStockView,
    EjecutarETLView,
    EntradaListCreateView,
    FeriadoListSyncView,
    InsumoDetailView,
    InsumoListCreateView,
    LoginView,
    MermaListCreateView,
    NotificacionListView,
    PerfilView,
    PermisoListView,
    RolListView,
    SalidaListCreateView,
    UsuarioGestionDetailView,
    UsuarioGestionListCreateView,
)

urlpatterns = [
    # Autenticacion y perfil del usuario conectado.
    path('login/', LoginView.as_view(), name='login'),
    path('perfil/', PerfilView.as_view(), name='perfil'),
    # Administracion de usuarios, roles y permisos.
    path('roles/', RolListView.as_view(), name='roles'),
    path('permisos/', PermisoListView.as_view(), name='permisos'),
    path('gestion/', UsuarioGestionListCreateView.as_view(), name='usuarios-gestion'),
    path('gestion/<int:id_usuario>/', UsuarioGestionDetailView.as_view(), name='usuarios-gestion-detalle'),
    # Modulos operativos de stock: catalogos, insumos, entradas, salidas y alertas.
    path('stock/catalogos/', CatalogoStockView.as_view(), name='stock-catalogos'),
    path('stock/insumos/', InsumoListCreateView.as_view(), name='stock-insumos'),
    path('stock/insumos/<int:id_insumo>/', InsumoDetailView.as_view(), name='stock-insumo-detalle'),
    path('stock/entradas/', EntradaListCreateView.as_view(), name='stock-entradas'),
    path('stock/salidas/', SalidaListCreateView.as_view(), name='stock-salidas'),
    path('stock/mermas/', MermaListCreateView.as_view(), name='stock-mermas'),
    path('stock/notificaciones/', NotificacionListView.as_view(), name='stock-notificaciones'),
    # Integracion externa y analitica para la cuarta iteracion.
    path('feriados/', FeriadoListSyncView.as_view(), name='feriados'),
    path('bi/etl/', EjecutarETLView.as_view(), name='bi-etl'),
    path('bi/dashboard/', BIDashboardView.as_view(), name='bi-dashboard'),
]
