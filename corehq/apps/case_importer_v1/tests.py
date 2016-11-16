import mock
from django.test import TestCase, SimpleTestCase
from django.test.utils import override_settings
from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases

from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.export.models import (
    CaseExportDataSchema,
    ExportGroupSchema,
    PathNode,
    ExportItem,
    MAIN_TABLE,
)
from corehq.apps.case_importer_v1.exceptions import ImporterError
from corehq.apps.case_importer_v1.tasks import do_import, bulk_import_async
from corehq.apps.case_importer_v1.util import ImporterConfig, is_valid_owner, get_case_properties_for_case_type
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests.util import delete_all_locations
from corehq.apps.users.models import WebUser, CommCareUser, DomainMembership
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors

from .const import ImportErrors


class ExcelFileFake(object):
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
        self.row_generator = row_generator or default_row_generator
        self.workbook = self.Workbook()

    def get_header_columns(self):
        return self.header_columns

    @property
    def max_row(self):
        return self.num_rows

    def iter_rows(self):
        for i in range(self.max_row):
            yield self._get_row(i)

    def _get_row(self, index):
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
        super(ImporterTest, self).setUp()
        self.domain = create_domain("importer-test").name
        self.default_case_type = 'importer-test-casetype'
        self.default_headers = ['case_id', 'age', 'sex', 'location']

        self.couch_user = WebUser.create(None, "test", "foobar")
        self.couch_user.add_domain_membership(self.domain, is_admin=True)
        self.couch_user.save()

        self.accessor = CaseAccessors(self.domain)

        self.factory = CaseFactory(domain=self.domain, case_defaults={
            'case_type': self.default_case_type,
        })
        delete_all_cases()

    def tearDown(self):
        self.couch_user.delete()
        delete_all_locations()
        LocationType.objects.all().delete()
        super(ImporterTest, self).tearDown()

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
            search_column=search_column,
            search_field=search_field,
            named_columns=named_columns,
            create_new_cases=create_new_cases,
            key_column='',
            value_column='',
        )

    @run_with_all_backends
    def testImportNone(self):
        res = bulk_import_async(self._config(), self.domain, None)
        self.assertEqual('Sorry, your session has expired. Please start over and try again.',
                         unicode(res['errors']))
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    @run_with_all_backends
    def testImporterErrors(self):
        with mock.patch('corehq.apps.case_importer_v1.tasks.importer_util.get_spreadsheet', side_effect=ImporterError()):
            res = bulk_import_async(self._config(), self.domain, None)
            self.assertEqual('The session containing the file you uploaded has expired - please upload a new one.',
                             unicode(res['errors']))
            self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    @run_with_all_backends
    def testImportBasic(self):
        config = self._config(self.default_headers)
        file = ExcelFileFake(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain)
        self.assertEqual(5, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertFalse(res['errors'])
        self.assertEqual(1, res['num_chunks'])
        case_ids = self.accessor.get_case_ids_in_domain()
        cases = list(self.accessor.get_cases(case_ids))
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

    @run_with_all_backends
    def testImportNamedColumns(self):
        config = self._config(self.default_headers, named_columns=True)
        file = ExcelFileFake(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain)
        # we create 1 less since we knock off the header column
        self.assertEqual(4, res['created_count'])
        self.assertEqual(4, len(self.accessor.get_case_ids_in_domain()))

    @run_with_all_backends
    def testImportTrailingWhitespace(self):
        cols = ['case_id', 'age', u'sex\xa0', 'location']
        config = self._config(cols, named_columns=True)
        file = ExcelFileFake(header_columns=cols, num_rows=2)
        res = do_import(file, config, self.domain)
        # we create 1 less since we knock off the header column
        self.assertEqual(1, res['created_count'])
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        case = self.accessor.get_case(case_ids[0])
        self.assertTrue(bool(case.get_case_property('sex')))  # make sure the value also got properly set

    @run_with_all_backends
    def testCaseIdMatching(self):
        # bootstrap a stub case
        [case] = self.factory.create_or_update_case(CaseStructure(attrs={
            'create': True,
            'update': {'importer_test_prop': 'foo'},
        }))
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))

        config = self._config(self.default_headers)
        file = ExcelFileFake(
            header_columns=self.default_headers,
            num_rows=3,
            row_generator=id_match_generator(case.case_id)
        )
        res = do_import(file, config, self.domain)
        self.assertEqual(0, res['created_count'])
        self.assertEqual(3, res['match_count'])
        self.assertFalse(res['errors'])

        # shouldn't create any more cases, just the one
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        [case] = self.accessor.get_cases(case_ids)
        for prop in self.default_headers[1:]:
            self.assertTrue(prop in case.get_case_property(prop))

        # shouldn't touch existing properties
        self.assertEqual('foo', case.get_case_property('importer_test_prop'))

    @run_with_all_backends
    def testCaseLookupTypeCheck(self):
        [case] = self.factory.create_or_update_case(CaseStructure(attrs={
            'create': True,
            'case_type': 'nonmatch-type',
        }))
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))
        config = self._config(self.default_headers)
        file = ExcelFileFake(header_columns=self.default_headers, num_rows=3,
                             row_generator=id_match_generator(case.case_id))
        res = do_import(file, config, self.domain)
        # because the type is wrong these shouldn't match
        self.assertEqual(3, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(4, len(self.accessor.get_case_ids_in_domain()))

    @run_with_all_backends
    def testCaseLookupDomainCheck(self):
        self.factory.domain = 'wrong-domain'
        [case] = self.factory.create_or_update_case(CaseStructure(attrs={
            'create': True,
        }))
        self.assertEqual(0, len(self.accessor.get_case_ids_in_domain()))
        config = self._config(self.default_headers)
        file = ExcelFileFake(
            header_columns=self.default_headers,
            num_rows=3,
            row_generator=id_match_generator(case.case_id)
        )
        res = do_import(file, config, self.domain)

        # because the domain is wrong these shouldn't match
        self.assertEqual(3, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(3, len(self.accessor.get_case_ids_in_domain()))

    @run_with_all_backends
    def testExternalIdMatching(self):
        # bootstrap a stub case
        external_id = 'importer-test-external-id'
        [case] = self.factory.create_or_update_case(CaseStructure(
            attrs={
                'create': True,
                'external_id': external_id,
            }
        ))
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))

        headers = ['external_id', 'age', 'sex', 'location']
        config = self._config(headers, search_field='external_id')
        file = ExcelFileFake(
            header_columns=headers,
            num_rows=3,
            row_generator=id_match_generator(external_id)
        )
        res = do_import(file, config, self.domain)
        self.assertEqual(0, res['created_count'])
        self.assertEqual(3, res['match_count'])
        self.assertFalse(res['errors'])

        # shouldn't create any more cases, just the one
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))

    @run_with_all_backends
    def test_external_id_matching_on_create_with_custom_column_name(self):
        headers = ['id_column', 'age', 'sex', 'location']
        external_id = 'external-id-test'
        config = self._config(headers[1:], search_column='id_column', search_field='external_id')
        file = ExcelFileFake(
            header_columns=headers,
            num_rows=2,
            row_generator=id_match_generator(external_id)
        )
        res = do_import(file, config, self.domain)
        self.assertEqual(1, res['created_count'])
        self.assertEqual(1, res['match_count'])
        self.assertFalse(res['errors'])
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        case = self.accessor.get_case(case_ids[0])
        self.assertEqual(external_id, case.external_id)

    def testNoCreateNew(self):
        config = self._config(self.default_headers, create_new_cases=False)
        file = ExcelFileFake(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain)

        # no matching and no create new set - should do nothing
        self.assertEqual(0, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    def testBlankRows(self):
        # don't create new cases for rows left blank
        config = self._config(self.default_headers, create_new_cases=True)
        file = ExcelFileFake(
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
        file = ExcelFileFake(header_columns=self.default_headers, num_rows=5)
        res = do_import(file, config, self.domain, chunksize=2)
        # 5 cases in chunks of 2 = 3 chunks
        self.assertEqual(3, res['num_chunks'])
        self.assertEqual(5, res['created_count'])
        self.assertEqual(5, len(get_case_ids_in_domain(self.domain)))

    @run_with_all_backends
    def testExternalIdChunking(self):
        # bootstrap a stub case
        external_id = 'importer-test-external-id'

        headers = ['external_id', 'age', 'sex', 'location']
        config = self._config(headers, search_field='external_id')
        file = ExcelFileFake(header_columns=headers, num_rows=3,
                             row_generator=id_match_generator(external_id))

        # the first one should create the case, and the remaining two should update it
        res = do_import(file, config, self.domain)
        self.assertEqual(1, res['created_count'])
        self.assertEqual(2, res['match_count'])
        self.assertFalse(res['errors'])
        self.assertEqual(2, res['num_chunks']) # the lookup causes an extra chunk

        # should just create the one case
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        [case] = self.accessor.get_cases(case_ids)
        self.assertEqual(external_id, case.external_id)
        for prop in self.default_headers[1:]:
            self.assertTrue(prop in case.get_case_property(prop))

    @run_with_all_backends
    def testParentCase(self):
        headers = ['parent_id', 'name', 'case_id']
        config = self._config(headers, create_new_cases=True, search_column='case_id')
        rows = 3
        [parent_case] = self.factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))

        file = ExcelFileFake(header_columns=headers,
                             num_rows=rows,
                             row_generator=id_match_generator(parent_case.case_id))
        file_missing = ExcelFileFake(header_columns=headers,
                                     num_rows=rows)

        # Should successfully match on `rows` cases
        res = do_import(file, config, self.domain)
        self.assertEqual(rows, res['created_count'])

        # Should be unable to find parent case on `rows` cases
        res = do_import(file_missing, config, self.domain)
        error_column_name = 'parent_id'
        self.assertEqual(rows,
                         len(res['errors'][ImportErrors.InvalidParentId][error_column_name]['rows']),
                         "All cases should have missing parent")

    def import_mock_file(self, rows):
        config = self._config(rows[0])
        case_rows = rows[1:]
        num_rows = len(case_rows)
        xls_file = ExcelFileFake(
            header_columns=rows[0],
            num_rows=num_rows,
            row_generator=lambda _, i: case_rows[i],
        )
        return do_import(xls_file, config, self.domain)

    @run_with_all_backends
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
        case_ids = self.accessor.get_case_ids_in_domain()
        cases = {c.name: c for c in list(self.accessor.get_cases(case_ids))}

        self.assertEqual(cases['location-owner-id'].owner_id, location.group_id)
        self.assertEqual(cases['location-owner-code'].owner_id, location.group_id)
        self.assertEqual(cases['location-owner-name'].owner_id, location.group_id)

        error_message = ImportErrors.DuplicateLocationName
        error_column_name = None
        self.assertIn(error_message, res['errors'])
        self.assertEqual(res['errors'][error_message][error_column_name]['rows'], [4])

        error_message = ImportErrors.InvalidOwnerId
        self.assertIn(error_message, res['errors'])
        error_column_name = 'owner_id'
        self.assertEqual(res['errors'][error_message][error_column_name]['rows'], [5])


class ImporterUtilsTest(SimpleTestCase):

    def test_user_owner_match(self):
        self.assertTrue(is_valid_owner(_mk_user(domain='match'), 'match'))

    def test_user_owner_nomatch(self):
        self.assertFalse(is_valid_owner(_mk_user(domain='match'), 'nomatch'))

    def test_web_user_owner_match(self):
        self.assertTrue(is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'match'))
        self.assertTrue(is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'match2'))

    def test_web_user_owner_nomatch(self):
        self.assertFalse(is_valid_owner(_mk_web_user(domains=['match', 'match2']), 'nomatch'))

    @override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
    def test_get_case_properties_for_case_type(self):
        schema = CaseExportDataSchema(
            group_schemas=[
                ExportGroupSchema(
                    path=MAIN_TABLE,
                    items=[
                        ExportItem(
                            path=[PathNode(name='name')],
                            label='name',
                            last_occurrences={},
                        ),
                        ExportItem(
                            path=[PathNode(name='color')],
                            label='color',
                            last_occurrences={},
                        ),
                    ],
                    last_occurrences={},
                ),
            ],
        )

        with mock.patch(
                'corehq.apps.export.models.new.CaseExportDataSchema.generate_schema_from_builds',
                return_value=schema):
            case_types = get_case_properties_for_case_type('test-domain', 'case-type')

        self.assertEqual(sorted(case_types), ['color', 'name'])


def _mk_user(domain):
    return CommCareUser(domain=domain, domain_membership=DomainMembership(domain=domain))


def _mk_web_user(domains):
    return WebUser(domains=domains, domain_memberships=[DomainMembership(domain=domain) for domain in domains])
