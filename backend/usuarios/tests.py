from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Categoria, Entrada, Insumo, Merma, Rol, Salida, Stock, UnidadMedida, Usuario
from .models import HechoMovimientoStock
from .etl import ejecutar_etl_movimientos_stock


class MovimientosTests(TestCase):
    def setUp(self):
        rol, _ = Rol.objects.get_or_create(nombre_rol='ayudante_cocina')
        self.user = Usuario.objects.create_user(username='operador-prueba', id_rol=rol)
        self.other = Usuario.objects.create_user(username='otro-prueba', id_rol=rol)
        categoria, _ = Categoria.objects.get_or_create(nombre_categoria='Pruebas')
        unidad, _ = UnidadMedida.objects.get_or_create(nombre_unidad='Unidad de prueba')
        self.insumo = Insumo.objects.create(nombre='Insumo de prueba', id_categoria=categoria, id_unidad=unidad, stock_minimo=5)
        self.stock = Stock.objects.create(id_insumo=self.insumo, cantidad_actual=10)
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def post(self, kind, payload):
        return self.client.post(f'/api/usuarios/stock/{kind}/', payload, format='json')

    def payload(self, kind):
        if kind == 'mermas':
            return {'id_operacion': 'merma-test', 'id_insumo': self.insumo.pk, 'cantidad': 5, 'motivo': 'Recorte'}
        return {'id_operacion': f'{kind}-test', 'detalles': [{'id_insumo': self.insumo.pk, 'cantidad': 5}]}

    def test_reintentos_no_duplican_movimientos_ni_stock(self):
        for kind, model, expected in [('entradas', Entrada, 15), ('salidas', Salida, 5), ('mermas', Merma, 5)]:
            with self.subTest(kind=kind):
                self.stock.cantidad_actual = 10
                self.stock.save()
                before = model.objects.count()
                payload = self.payload(kind)
                first = self.post(kind, payload)
                second = self.post(kind, payload)
                self.assertEqual(first.status_code, 201, first.data)
                self.assertEqual(second.status_code, 200, second.data)
                self.assertEqual(first.data, second.data)
                self.assertEqual(model.objects.count(), before + 1)
                self.stock.refresh_from_db()
                self.assertEqual(self.stock.cantidad_actual, expected)

    def test_identificador_no_expone_movimiento_de_otro_usuario(self):
        payload = self.payload('entradas')
        self.assertEqual(self.post('entradas', payload).status_code, 201)
        self.client.force_authenticate(self.other)
        self.assertEqual(self.post('entradas', payload).status_code, 409)

    def test_reintento_con_datos_distintos_es_conflicto(self):
        payload = self.payload('entradas')
        self.assertEqual(self.post('entradas', payload).status_code, 201)
        payload['detalles'][0]['cantidad'] = 9
        self.assertEqual(self.post('entradas', payload).status_code, 409)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, 15)

    def test_salida_respeta_minimo_y_merma_disponibilidad(self):
        payload = self.payload('salidas')
        payload['detalles'][0]['cantidad'] = 6
        self.assertEqual(self.post('salidas', payload).status_code, 400)
        payload = self.payload('mermas')
        payload['cantidad'] = 11
        self.assertEqual(self.post('mermas', payload).status_code, 400)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, 10)

    def test_cantidades_negativas_no_invierten_el_stock(self):
        for kind in ['entradas', 'salidas']:
            payload = self.payload(kind)
            payload['detalles'][0]['cantidad'] = -1
            self.assertEqual(self.post(kind, payload).status_code, 400)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, Decimal('10'))

    def test_clientes_sin_id_operacion_siguen_funcionando(self):
        payload = self.payload('entradas')
        del payload['id_operacion']
        self.assertEqual(self.post('entradas', payload).status_code, 201)

    def test_entrada_con_merma_descuenta_stock_y_registra_perdida(self):
        payload = self.payload('entradas')
        payload['detalles'][0].update(cantidad=2, costo_unitario=40)
        payload['mermas'] = [
            {
                'id_insumo': self.insumo.pk,
                'cantidad': 1,
                'observacion': 'Producto danado al recibir',
            }
        ]
        response = self.post('entradas', payload)
        self.assertEqual(response.status_code, 201, response.data)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, Decimal('11'))
        merma = Merma.objects.get()
        self.assertEqual(merma.motivo, 'Recepción')
        self.assertEqual(merma.cantidad, Decimal('1.000'))

    def test_entrada_rechaza_merma_mayor_a_cantidad_recibida(self):
        payload = self.payload('entradas')
        payload['detalles'][0].update(cantidad=2, costo_unitario=40)
        payload['mermas'] = [
            {
                'id_insumo': self.insumo.pk,
                'cantidad': 3,
                'observacion': 'Producto danado al recibir',
            }
        ]
        self.assertEqual(self.post('entradas', payload).status_code, 400)
        self.stock.refresh_from_db()
        self.assertEqual(self.stock.cantidad_actual, Decimal('10'))

    def test_dashboard_actualiza_data_mart_y_reporta_merma_de_entrada(self):
        self.stock.cantidad_actual = 0
        self.stock.save()

        entrada_previa = self.payload('entradas')
        entrada_previa['id_operacion'] = 'entrada-previa-test'
        entrada_previa['detalles'][0].update(cantidad=10, costo_unitario=5)
        self.assertEqual(self.post('entradas', entrada_previa).status_code, 201)

        payload = self.payload('entradas')
        payload['id_operacion'] = 'entrada-merma-recepcion-test'
        payload['detalles'][0].update(cantidad=13, costo_unitario=25)
        payload['mermas'] = [
            {
                'id_insumo': self.insumo.pk,
                'cantidad': 4,
                'observacion': 'Merma registrada al recibir',
            }
        ]
        self.assertEqual(self.post('entradas', payload).status_code, 201)

        rol_propietario, _ = Rol.objects.get_or_create(nombre_rol='propietario')
        propietario = Usuario.objects.create_user(username='propietario-bi-prueba', id_rol=rol_propietario)
        self.client.force_authenticate(propietario)
        response = self.client.get('/api/usuarios/bi/dashboard/')

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(HechoMovimientoStock.objects.filter(origen='merma').count(), 1)
        self.assertEqual(Decimal(str(response.data['resumen']['total_mermas'])), Decimal('4.000'))
        self.assertEqual(Decimal(str(response.data['resumen']['costo_merma'])), Decimal('100.000'))
        self.assertEqual(response.data['merma_mensual'][0]['total'], Decimal('4.000'))
        self.assertEqual(response.data['merma_mensual'][0]['costo'], Decimal('100.000'))

    def test_websocket_solo_anuncia_nuevos_movimientos(self):
        with patch('usuarios.serializers.enviar_movimiento_stock') as notify:
            with self.captureOnCommitCallbacks(execute=True):
                self.post('entradas', self.payload('entradas'))
                self.post('entradas', self.payload('entradas'))
            self.assertEqual(notify.call_count, 1)

    def test_sincronizacion_conserva_fecha_del_registro_offline(self):
        fecha = timezone.now() - timedelta(days=1)
        payload = self.payload('entradas')
        payload['fecha_operacion'] = fecha.isoformat()
        self.assertEqual(self.post('entradas', payload).status_code, 201)
        self.assertEqual(Entrada.objects.get(id_operacion=payload['id_operacion']).fecha_entrada, fecha)

    def test_no_admite_fecha_futura(self):
        payload = self.payload('entradas')
        payload['fecha_operacion'] = (timezone.now() + timedelta(days=1)).isoformat()
        self.assertEqual(self.post('entradas', payload).status_code, 400)

    def test_permisos_del_chef_no_permiten_registrar_entradas(self):
        rol, _ = Rol.objects.get_or_create(nombre_rol='chef')
        chef = Usuario.objects.create_user(username='chef-prueba', id_rol=rol)
        self.client.force_authenticate(chef)
        self.assertEqual(self.post('entradas', self.payload('entradas')).status_code, 403)

    def test_chef_puede_actualizar_stock_minimo(self):
        rol, _ = Rol.objects.get_or_create(nombre_rol='chef')
        chef = Usuario.objects.create_user(username='chef-stock-prueba', id_rol=rol)
        self.client.force_authenticate(chef)
        response = self.client.patch(
            f'/api/usuarios/stock/insumos/{self.insumo.pk}/',
            {'stock_minimo': 7},
            format='json',
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.insumo.refresh_from_db()
        self.assertEqual(self.insumo.stock_minimo, Decimal('7'))

    def test_chef_no_gestiona_mermas_y_propietario_puede_consultarlas(self):
        rol_chef, _ = Rol.objects.get_or_create(nombre_rol='chef')
        chef = Usuario.objects.create_user(username='chef-merma-prueba', id_rol=rol_chef)
        self.client.force_authenticate(chef)
        self.assertEqual(self.client.get('/api/usuarios/stock/mermas/').status_code, 403)
        self.assertEqual(self.post('mermas', self.payload('mermas')).status_code, 403)

        rol_propietario, _ = Rol.objects.get_or_create(nombre_rol='propietario')
        propietario = Usuario.objects.create_user(username='propietario-merma-prueba', id_rol=rol_propietario)
        self.client.force_authenticate(propietario)
        self.assertEqual(self.client.get('/api/usuarios/stock/mermas/').status_code, 200)

    def test_etl_conserva_costos_ventas_y_stock_sin_duplicar(self):
        self.stock.cantidad_actual = 0
        self.stock.save()
        entrada = self.payload('entradas')
        entrada['detalles'][0].update(cantidad=20, costo_unitario=2)
        salida = self.payload('salidas')
        salida.update(cantidad_platos=1, total_venta_estimado=90)
        merma = self.payload('mermas')
        merma['cantidad'] = 2
        for kind, payload in [('entradas', entrada), ('salidas', salida), ('mermas', merma)]:
            self.assertEqual(self.post(kind, payload).status_code, 201)
        for _ in range(2):
            ejecutar_etl_movimientos_stock()
            hechos = HechoMovimientoStock.objects.filter(id_dim_insumo__nombre=self.insumo.nombre)
            self.assertEqual(hechos.count(), 3)
            self.assertEqual(hechos.get(origen='entrada').costo_total, 40)
            self.assertEqual(hechos.get(origen='salida').costo_total, 10)
            self.assertEqual(hechos.get(origen='salida').venta_total, 90)
            self.assertEqual(hechos.get(origen='merma').stock_resultante, 13)
