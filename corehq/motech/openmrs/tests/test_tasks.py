import datetime
import json
import logging
from contextlib import contextmanager
from unittest import skip

from django.conf import settings
from django.test import TestCase

import pytz
from mock import patch
from nose.tools import assert_raises_regexp

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.apps.locations.tests.util import LocationHierarchyTestCase
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.motech.const import BASIC_AUTH
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.openmrs.const import IMPORT_FREQUENCY_MONTHLY
from corehq.motech.openmrs.models import OpenmrsImporter
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.openmrs.tasks import (
    get_case_properties,
    import_patients_with_importer,
    poll_openmrs_atom_feeds,
)

TEST_DOMAIN = 'test-domain'


@contextmanager
def get_importer(column_mapping=None):
    importer_dict = {
        'domain': TEST_DOMAIN,
        'server_url': 'http://www.example.com/openmrs',
        'username': 'admin',
        'password': 'Admin123',
        'notify_addresses_str': 'admin@example.com',
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
            {
                'column': 'filhos',
                'commcare_data_type': 'cc_integer',
                'property': 'numero_de_filhos'
            },
            {
                'column': 'testados',
                'commcare_data_type': 'cc_integer',
                'property': 'numero_de_filhos_testados'
            },
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
                'commcare_data_type': 'cc_date',
                'property': 'data_proxima_consulta'
            }
        ],
    }
    if column_mapping:
        for mapping in importer_dict['column_map']:
            if mapping['column'] == column_mapping['column']:
                mapping.update(column_mapping)
                break
        else:
            importer_dict['column_map'].append(column_mapping)
    importer = OpenmrsImporter.wrap(importer_dict)
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
            'data_proxima_consulta': '2019-03-03',
            'data_ultima_consulta': '2019-02-25T00:00:00+02:00',
            'distrito': 'Matola',
            'estado_tarv': 'pre-TARV',
            'genero': 'M',
            'gravida': 'FALSE',
            'nid': '01234567/12/01234',
            'nome': 'David John',
            'numero_conviventes': None,
            'numero_de_filhos': 3,
            'numero_de_filhos_positivos': None,
            'numero_de_filhos_testados': 3,
            'parceiro_serologia': 'positive',
            'provincia': 'Maputo',
            'tarv_elegivel': 1
        }


def test_bad_data_type():
    """
    Notify if column data type is wrong
    """
    patient = get_patient()
    bad_column_mapping = {
        'column': 'data_proxima_consulta',
        'data_type': 'omrs_datetime',
        'commcare_data_type': 'cc_date',
        'property': 'data_proxima_consulta'
    }
    with get_importer(bad_column_mapping) as importer:
        with assert_raises_regexp(
            ConfigurationError,
            'Errors importing from <OpenmrsImporter None admin@http://www.example.com/openmrs>:\n'
            'Unable to deserialize value 1551564000000 '
            'in column "data_proxima_consulta" '
            'for case property "data_proxima_consulta". '
            'OpenMRS data type is given as "omrs_datetime". '
            'CommCare data type is given as "cc_date": '
            "argument of type 'int' is not iterable"
        ):
            get_case_properties(patient, importer)


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


class OwnerTests(LocationHierarchyTestCase):

    domain = TEST_DOMAIN
    location_type_names = ['province', 'city', 'suburb']
    location_structure = [
        ('Western Cape', [('Cape Town', [('Gardens', [])])]),
        ('Gauteng', [('Johannesburg', [])])
    ]

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.web_user = WebUser.create(TEST_DOMAIN, 'user1', '***', None, None)
        cls.mobile_worker = CommCareUser.create(TEST_DOMAIN, 'chw1', '***', None, None)
        cls.group = Group.wrap({
            'domain': TEST_DOMAIN,
            'name': 'group',
            'case_sharing': True
        })
        cls.group.save()
        cls.bad_group = Group.wrap({
            'domain': TEST_DOMAIN,
            'name': 'bad_group',
            'case_sharing': False
        })
        cls.bad_group.save()

    def setUp(self):
        self.send_mail_patcher = patch('corehq.motech.requests.send_mail_async')
        self.send_mail_mock = self.send_mail_patcher.start()
        self.import_patcher = patch('corehq.motech.openmrs.tasks.import_patients_of_owner')
        self.import_mock = self.import_patcher.start()
        self.decrypt_patcher = patch('corehq.motech.openmrs.tasks.b64_aes_decrypt')
        self.decrypt_patcher.start()

    def tearDown(self):
        self.decrypt_patcher.stop()
        self.import_patcher.stop()
        self.send_mail_patcher.stop()

    @classmethod
    def tearDownClass(cls):
        cls.bad_group.delete()
        cls.group.delete()
        cls.mobile_worker.delete()
        cls.web_user.delete()
        super().tearDownClass()

    def test_location_owner(self):
        """
        Setting owner_id to a location should not throw an error
        """
        with get_importer() as importer:
            importer.owner_id = self.locations['Gardens'].location_id
            import_patients_with_importer(importer.to_json())
            self.import_mock.assert_called()

    def test_commcare_user_owner(self):
        """
        Setting owner_id to a mobile worker should not throw an error
        """
        with get_importer() as importer:
            importer.owner_id = self.mobile_worker.user_id
            import_patients_with_importer(importer.to_json())
            self.import_mock.assert_called()

    def test_web_user_owner(self):
        """
        Setting owner_id to a web user should not throw an error
        """
        with get_importer() as importer:
            importer.owner_id = self.web_user.user_id
            import_patients_with_importer(importer.to_json())
            self.import_mock.assert_called()

    def test_group_owner(self):
        """
        Setting owner_id to a case-sharing group should not throw an error
        """
        with get_importer() as importer:
            importer.owner_id = self.group._id
            import_patients_with_importer(importer.to_json())
            self.import_mock.assert_called()

    def test_bad_owner(self):
        """
        Notify on invalid owner_id
        """
        with get_importer() as importer:
            self.assertEqual(importer.owner_id, '123456')
            import_patients_with_importer(importer.to_json())
            self.send_mail_mock.delay.assert_called_with(
                'MOTECH Error',

                'Error importing patients for project space "test-domain" from '
                'OpenMRS Importer "<OpenmrsImporter None admin@http://www.example.com/openmrs>": '
                'owner_id "123456" is invalid.\r\n'
                'Project space: test-domain\r\n'
                'Remote API base URL: http://www.example.com/openmrs',

                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['admin@example.com'],
            )

    def test_bad_group(self):
        """
        Notify if owner_id is set to a NON-case-sharing group
        """
        with get_importer() as importer:
            importer.owner_id = self.bad_group._id
            import_patients_with_importer(importer.to_json())
            self.send_mail_mock.delay.assert_called_with(
                'MOTECH Error',

                'Error importing patients for project space "test-domain" from '
                'OpenMRS Importer "<OpenmrsImporter None admin@http://www.example.com/openmrs>": '
                f'owner_id "{importer.owner_id}" is invalid.\r\n'
                'Project space: test-domain\r\n'
                'Remote API base URL: http://www.example.com/openmrs',

                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=['admin@example.com'],
            )


@skip("Skip tests that use live third-party APIs")
class OpenmrsAtomFeedsTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain(TEST_DOMAIN)
        cls.location_type = LocationType.objects.create(
            domain=TEST_DOMAIN,
            name='test_location_type',
        )
        cls.location = SQLLocation.objects.create(
            domain=TEST_DOMAIN,
            name='test location',
            location_id='test_location',
            location_type=cls.location_type,
        )
        cls.user = CommCareUser.create(TEST_DOMAIN, 'username', 'password', None, None, location=cls.location)
        cls.repeater = OpenmrsRepeater.wrap({
            "domain": TEST_DOMAIN,
            "url": "https://demo.mybahmni.org/openmrs/",
            "auth_type": BASIC_AUTH,
            "username": "superman",
            "password": "Admin123",
            "white_listed_case_types": ["case"],
            "location_id": cls.location.location_id,
            "atom_feed_enabled": True,
            "openmrs_config": {
                "openmrs_provider": "",
                "case_config": {},
                "form_configs": []
            }
        })
        cls.repeater.save()

    @classmethod
    def tearDownClass(cls):
        cls.repeater.delete()
        cls.user.delete()
        cls.location.delete()
        cls.location_type.delete()
        cls.domain.delete()
        super().tearDownClass()

    def atom_feed_sanity_test(self):
        poll_openmrs_atom_feeds(TEST_DOMAIN)
