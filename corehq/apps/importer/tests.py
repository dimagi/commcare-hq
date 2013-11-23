from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import delete_all_cases
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import get_case_ids_in_domain, get_cases_in_domain
from corehq.apps.importer.tasks import do_import
from corehq.apps.importer.util import ImporterConfig
from corehq.apps.users.models import WebUser


class MockExcelFile(object):
    """
    Provides the minimal API of ExcelFile used by the importer
    """

    def __init__(self, header_columns=None, num_rows=0, has_errors=False, row_generator=None):
        self.header_columns = header_columns or []
        self.num_rows = num_rows
        self.has_errors = has_errors
        if row_generator is None:
            # by default, just return [propertyname-rowid] for every cell
            def row_generator(self, index):
                return ['{col}-{row}'.format(row=index, col=col) for col in self.header_columns]
        self.row_generator = row_generator

    def get_header_columns(self):
        return self.header_columns

    def get_num_rows(self):
        return self.num_rows

    def get_row(self, index):
        return self.row_generator(self, index)

class ImporterTest(TestCase):

    def setUp(self):
        self.domain = create_domain("importer-test").name
        self.default_case_type = 'importer-test-casetype'
        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(self.domain, is_admin=True)
        self.couch_user.save()
        delete_all_cases()

    def tearDown(self):
        self.couch_user.delete()

    def _config(self, col_names=None, search_column=None, case_type=None,
                search_field='case_id', named_columns=False, create_new_cases=True):
        col_names = col_names or ['case_id']
        case_type = case_type or self.default_case_type
        search_column = search_column or col_names[0]
        return ImporterConfig(
            couch_user_id=self.couch_user._id,
            case_type=case_type,
            excel_fields=col_names,
            case_fields=[''] * len(col_names),
            custom_fields=col_names,
            type_fields=['plain'] * len(col_names),
            search_column=search_column,
            search_field=search_field,
            named_columns=named_columns,
            create_new_cases=create_new_cases,
            key_column='',
            value_column='',
        )

    def testImportNone(self):
        res = do_import(None, self._config(), self.domain)
        self.assertEqual('EXPIRED', res['error'])
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    def testImporterErrors(self):
        res = do_import(MockExcelFile(has_errors=True), self._config(), self.domain)
        self.assertEqual('HAS_ERRORS', res['error'])
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    def testImportBasic(self):
        headers = ['case_id', 'age', 'sex', 'location']
        config = self._config(headers)
        file = MockExcelFile(header_columns=headers, num_rows=5)
        res = do_import(file, config, self.domain)
        self.assertEqual(5, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, res['errors'])
        cases = list(get_cases_in_domain(self.domain))
        self.assertEqual(5, len(cases))
        properties_seen = set()
        for case in cases:
            self.assertEqual(self.couch_user._id, case.user_id)
            self.assertEqual(self.couch_user._id, case.owner_id)
            self.assertEqual(self.default_case_type, case.type)
            for prop in headers[1:]:
                self.assertTrue(prop in case.get_case_property(prop))
                self.assertFalse(case.get_case_property(prop) in properties_seen)
                properties_seen.add(case.get_case_property(prop))

    def testImportNamedColumns(self):
        headers = ['case_id', 'age', 'sex', 'location']
        config = self._config(headers, named_columns=True)
        file = MockExcelFile(header_columns=headers, num_rows=5)
        res = do_import(file, config, self.domain)
        # we create 1 less since we knock off the header column
        self.assertEqual(4, res['created_count'])
        self.assertEqual(4, len(get_case_ids_in_domain(self.domain)))

