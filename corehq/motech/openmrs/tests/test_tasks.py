import datetime
import json
import logging
from contextlib import contextmanager

import pytz
from mock import patch

from corehq.motech.openmrs.const import IMPORT_FREQUENCY_MONTHLY
from corehq.motech.openmrs.models import OpenmrsImporter
from corehq.motech.openmrs.tasks import get_case_properties


@contextmanager
def get_importer():
    importer = OpenmrsImporter.wrap({
        'domain': 'test-domain',
        'server_url': 'http://www.example.com/openmrs',
        'username': 'admin',
        'password': 'Admin123',
        'location_id': '',
        'import_frequency': IMPORT_FREQUENCY_MONTHLY,
        'log_level': logging.INFO,
        'timezone': 'Africa/Maputo',
        'report_uuid': 'c0ffee',
        'report_params': {},
        'case_type': 'patient',
        'owner_id': '123456',
        'location_type_name': '',
        'external_id_column': 'NID',
        'name_columns': 'nome_inicial apelido',
        'column_map': [
            {'column': 'NID', 'property': 'nid'},
            {'column': 'nome_inicial', 'property': 'nome'},
            {'column': 'apelido', 'property': 'apelido'},
            {'column': 'Telefone', 'property': 'contact_phone_number'},
            {'column': 'provincia', 'property': 'provincia'},
            {'column': 'distrito', 'property': 'distrito'},
            {'column': 'localidade', 'property': 'avenida'},
            {'column': 'bairro', 'property': 'bairro'},
            {'column': 'Referencia', 'property': 'celula'},
            {'column': 'genero', 'property': 'genero'},
            {'column': 'data_do_nacimento', 'property': 'data_do_nacimento'},
            {'column': 'filhos', 'property': 'numero_de_filhos'},
            {'column': 'testados', 'property': 'numero_de_filhos_testados'},
            {'column': 'positivos', 'property': 'numero_de_filhos_positivos'},
            {'column': 'serologia', 'property': 'parceiro_serologia'},
            {'column': 'conviventes', 'property': 'numero_conviventes'},
            {'column': 'tarv_elegivel', 'property': 'tarv_elegivel'},
            {'column': 'estado_tarv', 'property': 'estado_tarv'},
            {'column': 'gravida', 'property': 'gravida'},
            {'column': 'coinfectado', 'property': 'coinfectado'},
            {'column': 'a_faltar', 'property': 'a_faltar'},
            {
                'column': 'data_ultima_consulta',
                'data_type': 'posix_milliseconds',
                'property': 'data_ultima_consulta'
            },
            {
                'column': 'data_proxima_consulta',
                'data_type': 'posix_milliseconds',
                'property': 'data_proxima_consulta'
            }
        ],
    })
    try:
        yield importer
    finally:
        del importer


def get_patient():
    return json.loads("""{
        "NID": "01234567/12/01234",
        "Referencia": null,
        "TIPO_PACIENTE": "ELEGIVEL SEM TARV - VISITA 181-187",
        "Telefone": "811231234",
        "a_faltar": 0,
        "apelido": "Smith",
        "bairro": "Unidade H",
        "coinfectado": "FALSE",
        "conviventes": null,
        "data_do_nacimento": "1981-10-31",
        "data_proxima_consulta": 1551564000000,
        "data_ultima_consulta": 1551045600000,
        "distrito": "Matola",
        "estado_tarv": "pre-TARV",
        "filhos": 3.0,
        "genero": "M",
        "gravida": "FALSE",
        "localidade": null,
        "nome": "David John Smith",
        "nome_inicial": "David John",
        "ordem": 5,
        "ordem1": 2,
        "patient_id": 1234,
        "positivos": null,
        "provincia": "Maputo",
        "proximo_levantamento": null,
        "proximo_seguimento": 1551564000000,
        "serologia": "positive",
        "tarv_elegivel": 1,
        "testados": 3.0,
        "ultimo_levantamento": null,
        "ultimo_seguimento": 1551045600000
    }""")


def test_get_case_properties():
    """
    If given a patient as returned by an OpenMRS report, and an importer, then
    get_case_properties should return the case name and fields to update.
    """
    patient = get_patient()

    with get_importer() as importer:
        case_name, fields_to_update = get_case_properties(patient, importer)

        assert case_name == 'David John Smith'
        assert fields_to_update == {
            'a_faltar': 0,
            'apelido': 'Smith',
            'avenida': None,
            'bairro': 'Unidade H',
            'celula': None,
            'coinfectado': 'FALSE',
            'contact_phone_number': '811231234',
            'data_do_nacimento': '1981-10-31',
            'data_proxima_consulta': '2019-03-03T00:00:00+02:00',
            'data_ultima_consulta': '2019-02-25T00:00:00+02:00',
            'distrito': 'Matola',
            'estado_tarv': 'pre-TARV',
            'genero': 'M',
            'gravida': 'FALSE',
            'nid': '01234567/12/01234',
            'nome': 'David John',
            'numero_conviventes': None,
            'numero_de_filhos': 3.0,
            'numero_de_filhos_positivos': None,
            'numero_de_filhos_testados': 3.0,
            'parceiro_serologia': 'positive',
            'provincia': 'Maputo',
            'tarv_elegivel': 1
        }


@patch("corehq.motech.openmrs.models.get_timezone_for_domain")
def test_get_domain_timezone(get_timezone_for_domain_mock):
    """
    If importer.timezone has no value, importer.get_timezone() should
    return the domain's timezone
    """
    get_timezone_for_domain_mock.return_value = datetime.timezone.utc
    with get_importer() as importer:
        importer.timezone = ""
        timezone = importer.get_timezone()
        assert timezone == datetime.timezone.utc


@patch("corehq.motech.openmrs.models.get_timezone_for_domain")
def test_get_importer_timezone(get_timezone_for_domain_mock):
    """
    If importer.timezone has a value, importer.get_timezone() should
    return its timezone
    """
    get_timezone_for_domain_mock.return_value = datetime.timezone.utc
    cat = pytz.timezone("Africa/Maputo")
    with get_importer() as importer:
        importer.timezone = "Africa/Maputo"
        timezone = importer.get_timezone()
        assert timezone == cat
