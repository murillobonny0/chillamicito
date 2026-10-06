import json
from datetime import date
from urllib.request import Request, urlopen


NAGER_HOLIDAYS_URL = 'https://nagerholidays.com/api/v4/Holidays/{pais}/{anio}'
NAGER_DATE_URL = 'https://date.nager.at/api/v3/PublicHolidays/{anio}/{pais}'

# Diccionario local para mostrar nombres importantes de Bolivia en espanol.
NOMBRES_FERIADOS_BO = {
    '01-01': 'Año Nuevo',
    '01-06': 'Nacimiento del Estado Plurinacional',
    '02-02': 'Fiesta de la Virgen de Candelaria',
    '03-19': 'Día del Padre',
    '05-01': 'Día del Trabajador',
    '05-27': 'Día de la Madre',
    '06-21': 'Año Nuevo Andino',
    '08-02': 'Día de la Reforma Agraria',
    '08-06': 'Día de la Independencia',
    '09-14': 'Día de Cochabamba',
    '11-02': 'Día de Difuntos',
    '12-01': 'Promociones de fin de año',
    '12-15': 'Temporada de graduaciones',
    '12-25': 'Navidad',
    '12-31': 'Nochevieja',
}

# Fechas moviles de 2026 que se usan para planificacion del proyecto.
NOMBRES_VARIABLES_BO_2026 = {
    '2026-02-16': 'Lunes de Carnaval',
    '2026-02-17': 'Martes de Carnaval',
    '2026-04-02': 'Jueves Santo',
    '2026-04-03': 'Viernes Santo',
    '2026-06-04': 'Corpus Christi',
}

# Traducciones de respaldo cuando la API externa devuelve nombres en ingles.
TRADUCCIONES_NAGER_BO = {
    'new year': 'Año Nuevo',
    'plurinational state': 'Nacimiento del Estado Plurinacional',
    'candelaria': 'Fiesta de la Virgen de Candelaria',
    'carnival': 'Carnaval',
    'good friday': 'Viernes Santo',
    'labour day': 'Día del Trabajador',
    'labor day': 'Día del Trabajador',
    'corpus christi': 'Corpus Christi',
    'aymara new year': 'Año Nuevo Andino',
    'andean new year': 'Año Nuevo Andino',
    'agrarian reform': 'Día de la Reforma Agraria',
    'independence day': 'Día de la Independencia',
    'all souls': 'Día de Difuntos',
    'christmas': 'Navidad',
}


def obtener_feriados_api(anio=None, pais='BO'):
    """Consulta Nager.Date, normaliza nombres y agrega fechas comerciales locales."""
    anio = anio or date.today().year
    pais = pais.upper()
    data = _consultar_api(NAGER_HOLIDAYS_URL.format(pais=pais, anio=anio))
    if not data:
        data = _consultar_api(NAGER_DATE_URL.format(pais=pais, anio=anio))

    feriados = [
        {
            'fecha': item['date'],
            'nombre': _nombre_en_espanol(item, pais),
            'pais': item.get('countryCode', pais).upper(),
        }
        for item in data
        if item.get('date')
    ]
    feriados.extend(_eventos_planificacion_local(anio, pais))
    return _sin_duplicados(feriados)


def _consultar_api(url):
    """Realiza la peticion HTTP a la API externa y devuelve datos JSON."""
    request = Request(url, headers={'User-Agent': 'ChillamicitoStock/1.0'})
    try:
        with urlopen(request, timeout=12) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception:
        return []


def _nombre_en_espanol(item, pais):
    """Convierte el nombre del feriado a espanol."""
    nombre = item.get('localName') or item.get('name') or 'Feriado'
    fecha = item.get('date', '')

    if pais == 'BO':
        if fecha in NOMBRES_VARIABLES_BO_2026:
            return NOMBRES_VARIABLES_BO_2026[fecha]

        mes_dia = fecha[5:]
        if mes_dia in NOMBRES_FERIADOS_BO:
            return NOMBRES_FERIADOS_BO[mes_dia]

        nombre_normalizado = nombre.lower()
        for patron, traduccion in TRADUCCIONES_NAGER_BO.items():
            if patron in nombre_normalizado:
                return traduccion

    return nombre


def _eventos_planificacion_local(anio, pais):
    """Agrega fechas locales y comerciales que ayudan a estimar alta demanda."""
    if pais != 'BO':
        return []

    eventos = [
        ('01-01', 'Año Nuevo'),
        ('01-06', 'Nacimiento del Estado Plurinacional'),
        ('03-19', 'Día del Padre'),
        ('05-27', 'Día de la Madre'),
        ('08-06', 'Día de la Independencia'),
        ('09-14', 'Día de Cochabamba'),
        ('11-02', 'Día de Difuntos'),
        ('12-01', 'Promociones de fin de año'),
        ('12-15', 'Temporada de graduaciones'),
        ('12-25', 'Navidad'),
        ('12-31', 'Nochevieja'),
    ]

    if anio == 2026:
        eventos.extend(
            [
                ('02-16', 'Lunes de Carnaval'),
                ('02-17', 'Martes de Carnaval'),
                ('04-02', 'Jueves Santo'),
                ('04-03', 'Viernes Santo'),
                ('06-04', 'Corpus Christi'),
                ('06-21', 'Año Nuevo Andino'),
            ]
        )

    return [
        {
            'fecha': f'{anio}-{mes_dia}',
            'nombre': nombre,
            'pais': pais,
        }
        for mes_dia, nombre in eventos
    ]


def _sin_duplicados(feriados):
    """Elimina duplicados por fecha/pais y ordena el calendario resultante."""
    unicos = {}
    for feriado in feriados:
        unicos[(feriado['fecha'], feriado['pais'])] = feriado
    return sorted(unicos.values(), key=lambda item: item['fecha'])
