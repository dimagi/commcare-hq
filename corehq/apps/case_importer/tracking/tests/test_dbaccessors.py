from uuid import UUID
import uuid
from django.forms import model_to_dict
from django.test import TestCase
import mock
from casexml.apps.case.tests.util import delete_all_cases, delete_all_xforms
from corehq.apps.case_importer.tasks import do_import
from corehq.apps.case_importer.tests.test_importer import make_worksheet_wrapper
from corehq.apps.case_importer.tracking.case_upload_tracker import CaseUpload
from corehq.apps.case_importer.tracking.dbaccessors import get_case_upload_records, \
    get_case_ids_for_case_upload
from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.apps.case_importer.util import ImporterConfig
from corehq.apps.users.models import WebUser, CouchUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors


class DbaccessorsTest(TestCase):
    domain = 'test-case-importer-dbaccessors'

    @classmethod
    def setUpClass(cls):
        super(DbaccessorsTest, cls).setUpClass()
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
        super(DbaccessorsTest, cls).tearDownClass()

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


class FormAndCaseIdsTest(TestCase):
    case_type = 'test_case_ids'
    domain = 'form-and-case-ids-test'
    couch_user_id = 'lalalalalala'

    @classmethod
    def tearDownClass(cls):
        delete_all_cases()
        delete_all_xforms()
        super(FormAndCaseIdsTest, cls).tearDownClass()

    def _get_config(self, excel_fields):
        return ImporterConfig(
            couch_user_id=self.couch_user_id,
            case_type=self.case_type,
            excel_fields=excel_fields,
            case_fields=[''] * len(excel_fields),
            custom_fields=excel_fields,
            search_column=excel_fields[0],
            search_field='case_id',
            create_new_cases=True,
        )

    @mock.patch.object(CouchUser, 'get_by_user_id')
    def _import_rows(self, rows, get_by_user_id):
        get_by_user_id.return_value = WebUser(
            _id=self.couch_user_id, domain=self.domain, username='lalala@example.com')
        case_upload_record = CaseUploadRecord(
            upload_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            domain=self.domain,
        )
        case_upload_record.save()
        self.addCleanup(case_upload_record.delete)
        tracker = CaseUpload(case_upload_record.upload_id)
        # mock internals to have record_cases use our case_upload_record
        tracker.__dict__['_case_upload_record'] = case_upload_record

        config = self._get_config(rows[0])
        xls_file = make_worksheet_wrapper(*rows)
        do_import(xls_file, config, self.domain,
                  record_form_callback=tracker.record_form)

        return case_upload_record

    def test_order(self):
        data = [
            ['name'],
            ['john'],
            ['paul'],
            ['george'],
            ['ringo'],
        ]
        case_upload_record = self._import_rows(data)
        case_ids = list(get_case_ids_for_case_upload(case_upload_record))
        cases = CaseAccessors(self.domain).get_cases(case_ids, ordered=True)
        self.assertEqual(case_ids, [case.case_id for case in cases])
        should_match_original_data_order = [['name']] + [[case.name] for case in cases]
        self.assertEqual(should_match_original_data_order, data)
