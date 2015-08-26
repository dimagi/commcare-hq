from django.test import TestCase
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.tests import delete_all_cases

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain, \
    get_cases_in_domain
from corehq.apps.importer.tasks import do_import
from corehq.apps.importer.util import ImporterConfig
from corehq.apps.locations.models import LocationType
from corehq.apps.users.models import WebUser

from .const import ImportErrors

class MockExcelFile(object):
    """
    Provides the minimal API of ExcelFile used by the importer
    """
    class Workbook(object):
        def __init__(self):
            self._datemode = 0

        @property
        def datemode(self):
            return self._datemode

    def __init__(self, header_columns=None, num_rows=0, has_errors=False, row_generator=None):
        self.header_columns = header_columns or []
        self.num_rows = num_rows
        self.has_errors = has_errors
        self.row_generator = row_generator or default_row_generator
        self.workbook = self.Workbook()

    def get_header_columns(self):
        return self.header_columns

    def get_num_rows(self):
        return self.num_rows

    def get_row(self, index):
        return self.row_generator(self, index)

def default_row_generator(excel_file, index):
    # by default, just return [propertyname-rowid] for every cell
    return [u'{col}-{row}'.format(row=index, col=col) for col in excel_file.header_columns]

def blank_row_generator(excel_file, index):
    return [''.format(row=index, col=col) for col in excel_file.header_columns]

def id_match_generator(id):
    def match(excel_file, index):
        return [id] + ['{col}-{row}'.format(row=index, col=col) for col in excel_file.header_columns[1:]]
    return match

class ImporterTest(TestCase):

    def setUp(self):
        self.domain = create_domain("importer-test").name
        self.default_case_type = 'importer-test-casetype'
        self.default_headers = ['case_id', 'age', 'sex', 'location']

        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(self.domain, is_admin=True)
        self.couch_user.save()
        delete_all_cases()

    def tearDown(self):
        self.couch_user.delete()

    def _config(self, col_names=None, search_column=None, case_type=None,
                search_field='case_id', named_columns=False, create_new_cases=True):
        col_names = col_names or self.default_headers
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
        config = self._config(self.default_headers)
        file = MockExcelFile(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain)
        self.assertEqual(5, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertFalse(res['errors'])
        self.assertEqual(1, res['num_chunks'])
        cases = list(get_cases_in_domain(self.domain))
        self.assertEqual(5, len(cases))
        properties_seen = set()
        for case in cases:
            self.assertEqual(self.couch_user._id, case.user_id)
            self.assertEqual(self.couch_user._id, case.owner_id)
            self.assertEqual(self.default_case_type, case.type)
            for prop in self.default_headers[1:]:
                self.assertTrue(prop in case.get_case_property(prop))
                self.assertFalse(case.get_case_property(prop) in properties_seen)
                properties_seen.add(case.get_case_property(prop))

    def testImportNamedColumns(self):
        config = self._config(self.default_headers, named_columns=True)
        file = MockExcelFile(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain)
        # we create 1 less since we knock off the header column
        self.assertEqual(4, res['created_count'])
        self.assertEqual(4, len(get_case_ids_in_domain(self.domain)))

    def testImportTrailingWhitespace(self):
        cols = ['case_id', 'age', u'sex\xa0', 'location']
        config = self._config(cols, named_columns=True)
        file = MockExcelFile(header_columns=cols, num_rows=2)
        res = do_import(file, config, self.domain)
        # we create 1 less since we knock off the header column
        self.assertEqual(1, res['created_count'])
        case_ids = get_case_ids_in_domain(self.domain)
        self.assertEqual(1, len(case_ids))
        case = CommCareCase.get(case_ids[0])
        self.assertTrue(bool(case.sex))  # make sure the value also got properly set

    def testCaseIdMatching(self):
        # bootstrap a stub case
        case = CommCareCase(domain=self.domain, type=self.default_case_type)
        case.importer_test_prop = 'foo'
        case.save()
        self.assertEqual(1, len(get_case_ids_in_domain(self.domain)))

        config = self._config(self.default_headers)
        file = MockExcelFile(header_columns=self.default_headers, num_rows=3, row_generator=id_match_generator(case._id))
        res = do_import(file, config, self.domain)
        self.assertEqual(0, res['created_count'])
        self.assertEqual(3, res['match_count'])
        self.assertFalse(res['errors'])

        # shouldn't create any more cases, just the one
        self.assertEqual(1, len(get_case_ids_in_domain(self.domain)))
        [case] = get_cases_in_domain(self.domain)
        for prop in self.default_headers[1:]:
            self.assertTrue(prop in case.get_case_property(prop))

        # shouldn't touch existing properties
        self.assertEqual('foo', case.importer_test_prop)

    def testCaseLookupTypeCheck(self):
        case = CommCareCase(domain=self.domain, type='nonmatch-type')
        case.save()
        self.assertEqual(1, len(get_case_ids_in_domain(self.domain)))
        config = self._config(self.default_headers)
        file = MockExcelFile(header_columns=self.default_headers, num_rows=3,
                             row_generator=id_match_generator(case._id))
        res = do_import(file, config, self.domain)
        # because the type is wrong these shouldn't match
        self.assertEqual(3, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(4, len(get_case_ids_in_domain(self.domain)))

    def testCaseLookupDomainCheck(self):
        case = CommCareCase(domain='not-right-domain', type=self.default_case_type)
        case.save()
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))
        config = self._config(self.default_headers)
        file = MockExcelFile(header_columns=self.default_headers, num_rows=3,
                             row_generator=id_match_generator(case._id))
        res = do_import(file, config, self.domain)

        # because the domain is wrong these shouldn't match
        self.assertEqual(3, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(3, len(get_case_ids_in_domain(self.domain)))

    def testExternalIdMatching(self):
        # bootstrap a stub case
        case = CommCareCase(domain=self.domain, type=self.default_case_type)
        external_id = 'importer-test-external-id'
        case.external_id = external_id
        case.save()
        self.assertEqual(1, len(get_case_ids_in_domain(self.domain)))

        headers = ['external_id', 'age', 'sex', 'location']
        config = self._config(headers, search_field='external_id')
        file = MockExcelFile(header_columns=headers, num_rows=3,
                             row_generator=id_match_generator(external_id))
        res = do_import(file, config, self.domain)
        self.assertEqual(0, res['created_count'])
        self.assertEqual(3, res['match_count'])
        self.assertFalse(res['errors'])

        # shouldn't create any more cases, just the one
        self.assertEqual(1, len(get_case_ids_in_domain(self.domain)))

    def testNoCreateNew(self):
        config = self._config(self.default_headers, create_new_cases=False)
        file = MockExcelFile(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain)

        # no matching and no create new set - should do nothing
        self.assertEqual(0, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    def testBlankRows(self):
        # don't create new cases for rows left blank
        config = self._config(self.default_headers, create_new_cases=True)
        file = MockExcelFile(
            header_columns=self.default_headers,
            num_rows=5,
            row_generator=blank_row_generator
        )
        res = do_import(file, config, self.domain)

        # no matching and no create new set - should do nothing
        self.assertEqual(0, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    def testBasicChunking(self):
        config = self._config(self.default_headers)
        file = MockExcelFile(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain, chunksize=2)
        # 5 cases in chunks of 2 = 3 chunks
        self.assertEqual(3, res['num_chunks'])
        self.assertEqual(5, res['created_count'])
        self.assertEqual(5, len(get_case_ids_in_domain(self.domain)))

    def testExternalIdChunking(self):
        # bootstrap a stub case
        external_id = 'importer-test-external-id'

        headers = ['external_id', 'age', 'sex', 'location']
        config = self._config(headers, search_field='external_id')
        file = MockExcelFile(header_columns=headers, num_rows=3,
                             row_generator=id_match_generator(external_id))

        # the first one should create the case, and the remaining two should update it
        res = do_import(file, config, self.domain)
        self.assertEqual(1, res['created_count'])
        self.assertEqual(2, res['match_count'])
        self.assertFalse(res['errors'])
        self.assertEqual(2, res['num_chunks']) # the lookup causes an extra chunk

        # should just create the one case
        self.assertEqual(1, len(get_case_ids_in_domain(self.domain)))
        [case] = get_cases_in_domain(self.domain)
        self.assertEqual(external_id, case.external_id)
        for prop in self.default_headers[1:]:
            self.assertTrue(prop in case.get_case_property(prop))

    def testParentCase(self):
        headers = ['parent_id', 'name', 'case_id']
        config = self._config(headers, create_new_cases=True, search_column='case_id')
        rows = 3
        parent_case = CommCareCase(domain=self.domain, type=self.default_case_type)
        parent_case.save()

        file = MockExcelFile(header_columns=headers,
                             num_rows=rows,
                             row_generator=id_match_generator(parent_case['_id']))
        file_missing = MockExcelFile(header_columns=headers,
                                     num_rows=rows)

        # Should successfully match on `rows` cases
        res = do_import(file, config, self.domain)
        self.assertEqual(rows, res['created_count'])

        # Should be unable to find parent case on `rows` cases
        res = do_import(file_missing, config, self.domain)
        self.assertEqual(rows,
                         len(res['errors'][ImportErrors.InvalidParentId]['rows']),
                         "All cases should have missing parent")

    def import_mock_file(self, rows):
        config = self._config(rows[0])
        case_rows = rows[1:]
        num_rows = len(case_rows)
        xls_file = MockExcelFile(
            header_columns=rows[0],
            num_rows=num_rows,
            row_generator=lambda _, i: case_rows[i],
        )
        return do_import(xls_file, config, self.domain)

    def testLocationOwner(self):
        # This is actually testing several different things, but I figure it's
        # worth it, as each of these tests takes a non-trivial amount of time.
        non_case_sharing = LocationType.objects.create(
            domain=self.domain, name='lt1', shares_cases=False
        )
        case_sharing = LocationType.objects.create(
            domain=self.domain, name='lt2', shares_cases=True
        )
        location = make_loc('loc-1', 'Loc 1', self.domain, case_sharing)
        make_loc('loc-2', 'Loc 2', self.domain, case_sharing)
        duplicate_loc = make_loc('loc-3', 'Loc 2', self.domain, case_sharing)
        improper_loc = make_loc('loc-4', 'Loc 4', self.domain, non_case_sharing)

        res = self.import_mock_file([
            ['case_id', 'name', 'owner_id', 'owner_name'],
            ['', 'location-owner-id', location.group_id, ''],
            ['', 'location-owner-code', '', location.site_code],
            ['', 'location-owner-name', '', location.name],
            ['', 'duplicate-location-name', '', duplicate_loc.name],
            ['', 'non-case-owning-name', '', improper_loc.name],
        ])
        cases = {c.name: c for c in list(get_cases_in_domain(self.domain))}

        self.assertEqual(cases['location-owner-id'].owner_id, location.group_id)
        self.assertEqual(cases['location-owner-code'].owner_id, location.group_id)
        self.assertEqual(cases['location-owner-name'].owner_id, location.group_id)

        error_message = ImportErrors.DuplicateLocationName
        self.assertIn(error_message, res['errors'])
        self.assertEqual(res['errors'][error_message]['rows'], [4])

        error_message = ImportErrors.InvalidOwnerId
        self.assertIn(error_message, res['errors'])
        self.assertEqual(res['errors'][error_message]['rows'], [5])
