from django.test import TestCase
from corehq.apps.case_importer.tracking.dbaccessors import get_case_uploads
from corehq.apps.case_importer.tracking.models import CaseUploadRecord, CaseUploadJSON
from corehq.util.test_utils import DocTestMixin


class DbaccessorsTest(TestCase, DocTestMixin):
    domain = 'test-case-importer-dbaccessors'

    @classmethod
    def setUpClass(cls):
        cls.case_upload_1 = CaseUploadRecord(
            upload_id='7ca20e75-8ba3-4d0d-9c9c-66371e8895dc',
            task_id='a2ebc913-11e6-4b6b-b909-355a863e0682',
            domain=cls.domain,
        )
        cls.case_upload_2 = CaseUploadRecord(
            upload_id='63d07615-7f89-458e-863d-5f9b5f4f4b7b',
            task_id='fe47f168-0632-40d9-b01a-79612e98298b',
            domain=cls.domain,
        )
        cls.case_upload_1.save()
        cls.case_upload_2.save()

    @classmethod
    def tearDownClass(cls):
        cls.case_upload_1.delete()
        cls.case_upload_2.delete()

    def test_get_case_uploads(self):
        self.assert_doc_lists_equal(
            get_case_uploads(self.domain, limit=1),
            # gets latest
            [CaseUploadJSON.from_model(self.case_upload_2)])
        self.assert_doc_lists_equal(
            get_case_uploads(self.domain, limit=2),
            # gets latest first
            [CaseUploadJSON.from_model(self.case_upload_2),
             CaseUploadJSON.from_model(self.case_upload_1)])
