from unittest.mock import patch

from django.test import TestCase

from corehq.apps.data_dictionary.models import CaseType
from corehq.motech.models import ConnectionSettings
from corehq.util.test_utils import flag_enabled

from ..const import FHIR_VERSION_4_0_1
from ..models import FHIRImporter, FHIRImporterResourceType
from ..tasks import run_importer

DOMAIN = 'test-domain'


class TestRunImporter(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.conn = ConnectionSettings.objects.create(
            domain=DOMAIN,
            name='Test ConnectionSettings',
            url='https://example.com/api/',
        )
        cls.fhir_importer = FHIRImporter.objects.create(
            domain=DOMAIN,
            connection_settings=cls.conn,
            fhir_version=FHIR_VERSION_4_0_1,
        )
        cls.mother = CaseType.objects.create(
            domain=DOMAIN,
            name='mother',
        )
        cls.referral = CaseType.objects.create(
            domain=DOMAIN,
            name='referral',
        )

    @classmethod
    def tearDownClass(cls):
        cls.referral.delete()
        cls.mother.delete()
        cls.fhir_importer.delete()
        cls.conn.delete()
        super().tearDownClass()

    @flag_enabled('FHIR_INTEGRATION')
    def test_import_related_only(self):
        import_me = FHIRImporterResourceType.objects.create(
            fhir_importer=self.fhir_importer,
            name='ServiceRequest',
            case_type=self.referral,
            search_params={'status': 'active'},
        )
        FHIRImporterResourceType.objects.create(
            fhir_importer=self.fhir_importer,
            name='Patient',
            case_type=self.mother,
            import_related_only=True,  # Don't import me
        )
        with patch('corehq.motech.fhir.tasks.import_resource_type') as import_resource_type:
            run_importer(self.fhir_importer)

            import_resource_type.assert_called_once()
            call_arg_2 = import_resource_type.call_args[0][1]
            self.assertEqual(call_arg_2, import_me)
