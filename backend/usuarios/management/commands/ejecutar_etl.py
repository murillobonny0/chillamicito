from django.core.management.base import BaseCommand, CommandError

from usuarios.etl import ejecutar_etl_movimientos_stock


class Command(BaseCommand):
    """Ejecuta el ETL del Data Mart desde consola o un job programado."""

    help = 'Ejecuta el ETL de movimientos de stock para reconstruir el Data Mart.'

    def handle(self, *args, **options):
        try:
            resultado = ejecutar_etl_movimientos_stock()
        except Exception as exc:
            raise CommandError(f'Error durante el ETL: {exc}') from exc

        self.stdout.write(self.style.SUCCESS(f"Estado: {resultado.get('estado')}"))
        self.stdout.write(resultado.get('descripcion', 'ETL ejecutado.'))
        self.stdout.write(f"Entradas transformadas: {resultado.get('entradas', 0)}")
        self.stdout.write(f"Salidas transformadas: {resultado.get('salidas', 0)}")
        self.stdout.write(f"Mermas transformadas: {resultado.get('mermas', 0)}")
        self.stdout.write(f"Movimientos cargados: {resultado.get('movimientos', 0)}")
        self.stdout.write(f"Filas omitidas: {resultado.get('filas_omitidas', 0)}")
        self.stdout.write(f"Alertas de stock negativo: {resultado.get('alertas_stock_negativo', 0)}")
        self.stdout.write(f"Salidas sin costo: {resultado.get('salidas_sin_costo', 0)}")
