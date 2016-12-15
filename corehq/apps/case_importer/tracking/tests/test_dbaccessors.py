from uuid import UUID
from django.forms import model_to_dict
from django.test import TestCase
from corehq.apps.case_importer.tracking.dbaccessors import get_case_upload_records
from corehq.apps.case_importer.tracking.models import CaseUploadRecord


class DbaccessorsTest(TestCase):
    domain = 'test-case-importer-dbaccessors'

    @classmethod
    def setUpClass(cls):
        cls.case_upload_1 = CaseUploadRecord(
            upload_id=UUID('7ca20e75-8ba3-4d0d-9c9c-66371e8895dc'),
            task_id=UUID('a2ebc913-11e6-4b6b-b909-355a863e0682'),
            domain=cls.domain,
        )
        cls.case_upload_2 = CaseUploadRecord(
            upload_id=UUID('63d07615-7f89-458e-863d-5f9b5f4f4b7b'),
            task_id=UUID('fe47f168-0632-40d9-b01a-79612e98298b'),
            domain=cls.domain,
        )
        cls.case_upload_1.save()
        cls.case_upload_2.save()

    @classmethod
    def tearDownClass(cls):
        cls.case_upload_1.delete()
        cls.case_upload_2.delete()

    def assert_model_lists_equal(self, list_1, list_2):
        self.assertEqual([(type(model), model_to_dict(model)) for model in list_1],
                         [(type(model), model_to_dict(model)) for model in list_2])

    def test_get_case_uploads(self):
        self.assert_model_lists_equal(
            get_case_upload_records(self.domain, limit=1),
            # gets latest
            [self.case_upload_2])
        self.assert_model_lists_equal(
            get_case_upload_records(self.domain, limit=2),
            # gets latest first
            [self.case_upload_2,
             self.case_upload_1])
