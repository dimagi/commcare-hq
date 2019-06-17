from __future__ import absolute_import
from __future__ import unicode_literals

from contextlib import contextmanager

from celery import states
from celery.exceptions import Ignore
from django.test import TestCase
from django.utils.dateparse import parse_datetime
from mock import patch

from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases
from corehq.apps.case_importer import exceptions
from corehq.apps.case_importer.do_import import do_import
from corehq.apps.case_importer.tasks import bulk_import_async
from corehq.apps.case_importer.util import ImporterConfig, WorksheetWrapper
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.dbaccessors import get_case_ids_in_domain
from corehq.apps.locations.models import LocationType
from corehq.apps.users.models import CommCareUser, UserRole, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.util.test_utils import flag_enabled
from corehq.util.timezones.conversions import PhoneTime
from corehq.util.workbook_reading import make_worksheet


class ImporterTest(TestCase):

    def setUp(self):
        super(ImporterTest, self).setUp()
        self.domain_obj = create_domain("importer-test")
        self.domain = self.domain_obj.name
        self.default_case_type = 'importer-test-casetype'

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
        self.domain_obj.delete()
        super(ImporterTest, self).tearDown()

    def _config(self, col_names, search_column=None, case_type=None,
                search_field='case_id', create_new_cases=True):
        return ImporterConfig(
            couch_user_id=self.couch_user._id,
            case_type=case_type or self.default_case_type,
            excel_fields=col_names,
            case_fields=[''] * len(col_names),
            custom_fields=col_names,
            search_column=search_column or col_names[0],
            search_field=search_field,
            create_new_cases=create_new_cases,
        )

    @run_with_all_backends
    @patch('corehq.apps.case_importer.tasks.bulk_import_async.update_state')
    def testImportNone(self, update_state):
        res = bulk_import_async.delay(self._config(['anything']), self.domain, None)
        self.assertIsInstance(res.result, Ignore)
        update_state.assert_called_with(
            state=states.FAILURE,
            meta={'errors': 'Sorry, your session has expired. Please start over and try again.'})
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    @run_with_all_backends
    def testImportBasic(self):
        config = self._config(['case_id', 'age', 'sex', 'location'])
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            ['case_id-0', 'age-0', 'sex-0', 'location-0'],
            ['case_id-1', 'age-1', 'sex-1', 'location-1'],
            ['case_id-2', 'age-2', 'sex-2', 'location-2'],
            ['case_id-3', 'age-3', 'sex-3', 'location-3'],
            ['case_id-4', 'age-4', 'sex-4', 'location-4'],
        )
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
            for prop in ['age', 'sex', 'location']:
                self.assertTrue(prop in case.get_case_property(prop))
                self.assertFalse(case.get_case_property(prop) in properties_seen)
                properties_seen.add(case.get_case_property(prop))

    @run_with_all_backends
    def testImportNamedColumns(self):
        config = self._config(['case_id', 'age', 'sex', 'location'])
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            ['case_id-0', 'age-0', 'sex-0', 'location-0'],
            ['case_id-1', 'age-1', 'sex-1', 'location-1'],
            ['case_id-2', 'age-2', 'sex-2', 'location-2'],
            ['case_id-3', 'age-3', 'sex-3', 'location-3'],
        )
        res = do_import(file, config, self.domain)

        self.assertEqual(4, res['created_count'])
        self.assertEqual(4, len(self.accessor.get_case_ids_in_domain()))

    @run_with_all_backends
    def testImportTrailingWhitespace(self):
        cols = ['case_id', 'age', 'sex\xa0', 'location']
        config = self._config(cols)
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex\xa0', 'location'],
            ['case_id-0', 'age-0', 'sex\xa0-0', 'location-0'],
        )
        res = do_import(file, config, self.domain)

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

        config = self._config(['case_id', 'age', 'sex', 'location'])
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            [case.case_id, 'age-0', 'sex-0', 'location-0'],
            [case.case_id, 'age-1', 'sex-1', 'location-1'],
            [case.case_id, 'age-2', 'sex-2', 'location-2'],
        )
        res = do_import(file, config, self.domain)
        self.assertEqual(0, res['created_count'])
        self.assertEqual(3, res['match_count'])
        self.assertFalse(res['errors'])

        # shouldn't create any more cases, just the one
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        [case] = self.accessor.get_cases(case_ids)
        for prop in ['age', 'sex', 'location']:
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
        config = self._config(['case_id', 'age', 'sex', 'location'])
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            [case.case_id, 'age-0', 'sex-0', 'location-0'],
            [case.case_id, 'age-1', 'sex-1', 'location-1'],
            [case.case_id, 'age-2', 'sex-2', 'location-2'],
        )
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
        config = self._config(['case_id', 'age', 'sex', 'location'])
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            [case.case_id, 'age-0', 'sex-0', 'location-0'],
            [case.case_id, 'age-1', 'sex-1', 'location-1'],
            [case.case_id, 'age-2', 'sex-2', 'location-2'],
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
        file = make_worksheet_wrapper(
            ['external_id', 'age', 'sex', 'location'],
            ['importer-test-external-id', 'age-0', 'sex-0', 'location-0'],
            ['importer-test-external-id', 'age-1', 'sex-1', 'location-1'],
            ['importer-test-external-id', 'age-2', 'sex-2', 'location-2'],
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
        file = make_worksheet_wrapper(
            ['id_column', 'age', 'sex', 'location'],
            ['external-id-test', 'age-0', 'sex-0', 'location-0'],
            ['external-id-test', 'age-1', 'sex-1', 'location-1'],
        )

        res = do_import(file, config, self.domain)
        self.assertFalse(res['errors'])
        self.assertEqual(1, res['created_count'])
        self.assertEqual(1, res['match_count'])
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        case = self.accessor.get_case(case_ids[0])
        self.assertEqual(external_id, case.external_id)

    def testNoCreateNew(self):
        config = self._config(['case_id', 'age', 'sex', 'location'], create_new_cases=False)
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            ['case_id-0', 'age-0', 'sex-0', 'location-0'],
            ['case_id-1', 'age-1', 'sex-1', 'location-1'],
            ['case_id-2', 'age-2', 'sex-2', 'location-2'],
            ['case_id-3', 'age-3', 'sex-3', 'location-3'],
            ['case_id-4', 'age-4', 'sex-4', 'location-4'],
        )
        res = do_import(file, config, self.domain)

        # no matching and no create new set - should do nothing
        self.assertEqual(0, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    def testBlankRows(self):
        # don't create new cases for rows left blank
        config = self._config(['case_id', 'age', 'sex', 'location'], create_new_cases=True)
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            [None, None, None, None],
            ['', '', '', ''],
        )
        res = do_import(file, config, self.domain)

        # no matching and no create new set - should do nothing
        self.assertEqual(0, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, len(get_case_ids_in_domain(self.domain)))

    @patch('corehq.apps.case_importer.do_import.CASEBLOCK_CHUNKSIZE', 2)
    def testBasicChunking(self):
        config = self._config(['case_id', 'age', 'sex', 'location'])
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location'],
            ['case_id-0', 'age-0', 'sex-0', 'location-0'],
            ['case_id-1', 'age-1', 'sex-1', 'location-1'],
            ['case_id-2', 'age-2', 'sex-2', 'location-2'],
            ['case_id-3', 'age-3', 'sex-3', 'location-3'],
            ['case_id-4', 'age-4', 'sex-4', 'location-4'],
        )
        res = do_import(file, config, self.domain)
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
        file = make_worksheet_wrapper(
            ['external_id', 'age', 'sex', 'location'],
            ['importer-test-external-id', 'age-0', 'sex-0', 'location-0'],
            ['importer-test-external-id', 'age-1', 'sex-1', 'location-1'],
            ['importer-test-external-id', 'age-2', 'sex-2', 'location-2'],
        )

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
        for prop in ['age', 'sex', 'location']:
            self.assertTrue(prop in case.get_case_property(prop))

    @run_with_all_backends
    def testParentCase(self):
        headers = ['parent_id', 'name', 'case_id']
        config = self._config(headers, create_new_cases=True, search_column='case_id')
        rows = 3
        [parent_case] = self.factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))

        file = make_worksheet_wrapper(
            ['parent_id', 'name', 'case_id'],
            [parent_case.case_id, 'name-0', 'case_id-0'],
            [parent_case.case_id, 'name-1', 'case_id-1'],
            [parent_case.case_id, 'name-2', 'case_id-2'],
        )
        file_missing = make_worksheet_wrapper(
            ['parent_id', 'name', 'case_id'],
            ['parent_id-0', 'name-0', 'case_id-0'],
            ['parent_id-1', 'name-1', 'case_id-1'],
            ['parent_id-2', 'name-2', 'case_id-2'],
        )

        # Should successfully match on `rows` cases
        res = do_import(file, config, self.domain)
        self.assertEqual(rows, res['created_count'])

        # Should be unable to find parent case on `rows` cases
        res = do_import(file_missing, config, self.domain)
        error_column_name = 'parent_id'
        self.assertEqual(rows,
                         len(res['errors'][exceptions.InvalidParentId.title][error_column_name]['rows']),
                         "All cases should have missing parent")

    def import_mock_file(self, rows):
        config = self._config(rows[0])
        xls_file = make_worksheet_wrapper(*rows)
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
        location = make_loc('loc-1', 'Loc 1', self.domain, case_sharing.code)
        make_loc('loc-2', 'Loc 2', self.domain, case_sharing.code)
        duplicate_loc = make_loc('loc-3', 'Loc 2', self.domain, case_sharing.code)
        improper_loc = make_loc('loc-4', 'Loc 4', self.domain, non_case_sharing.code)

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

        error_message = exceptions.DuplicateLocationName.title
        error_column_name = None
        self.assertIn(error_message, res['errors'])
        self.assertEqual(res['errors'][error_message][error_column_name]['rows'], [5])

        error_message = exceptions.InvalidOwnerId.title
        self.assertIn(error_message, res['errors'])
        error_column_name = 'owner_id'
        self.assertEqual(res['errors'][error_message][error_column_name]['rows'], [6])

    @run_with_all_backends
    def test_opened_on(self):
        case = self.factory.create_case()
        new_date = '2015-04-30T14:41:53.000000Z'
        with flag_enabled('BULK_UPLOAD_DATE_OPENED'):
            self.import_mock_file([
                ['case_id', 'date_opened'],
                [case.case_id, new_date]
            ])
        case = CaseAccessors(self.domain).get_case(case.case_id)
        self.assertEqual(case.opened_on, PhoneTime(parse_datetime(new_date)).done())

    @run_with_all_backends
    def test_columns_and_rows_align(self):
        case_owner = CommCareUser.create(self.domain, 'username', 'pw')
        res = self.import_mock_file([
            ['case_id', 'name', '', 'favorite_color', 'owner_id'],
            ['', 'Jeff', '', 'blue', case_owner._id],
            ['', 'Caroline', '', 'yellow', case_owner._id],
        ])
        self.assertEqual(res['errors'], {})

        case_ids = self.accessor.get_case_ids_in_domain()
        cases = {c.name: c for c in list(self.accessor.get_cases(case_ids))}
        self.assertEqual(cases['Jeff'].owner_id, case_owner._id)
        self.assertEqual(cases['Jeff'].get_case_property('favorite_color'), 'blue')
        self.assertEqual(cases['Caroline'].owner_id, case_owner._id)
        self.assertEqual(cases['Caroline'].get_case_property('favorite_color'), 'yellow')

    def test_user_can_access_location(self):
        with make_business_units(self.domain) as (inc, dsi, dsa), \
                restrict_user_to_location(self, dsa):
            table = """
                case_id | name            | owner_id
                        | Leonard Nimoy   | {inc}
                        | Kapil Dev       | {dsi}
                        | Quinton Fortune | {dsa}
            """.format(inc=inc.group_id, dsi=dsi.group_id, dsa=dsa.group_id)
            res = self.import_mock_file(_get_rows(table))

        case_ids = self.accessor.get_case_ids_in_domain()
        cases = {c.name: c for c in list(self.accessor.get_cases(case_ids))}
        self.assertEqual(cases['Quinton Fortune'].owner_id, dsa.group_id)
        self.assertTrue(res['errors'])
        error_message = exceptions.InvalidOwnerId.title
        error_col = 'owner_id'
        self.assertEqual(res['errors'][error_message][error_col]['rows'], [2, 3])

    def test_user_can_access_owner(self):
        with make_business_units(self.domain) as (inc, dsi, dsa), \
                restrict_user_to_location(self, dsa):
            inc_owner = CommCareUser.create(self.domain, 'inc', 'pw', location=inc)
            dsi_owner = CommCareUser.create(self.domain, 'dsi', 'pw', location=dsi)
            dsa_owner = CommCareUser.create(self.domain, 'dsa', 'pw', location=dsa)
            table = """
                case_id | name            | owner_id
                        | Leonard Nimoy   | {inc}
                        | Kapil Dev       | {dsi}
                        | Quinton Fortune | {dsa}
            """.format(inc=inc_owner._id, dsi=dsi_owner._id, dsa=dsa_owner._id)
            res = self.import_mock_file(_get_rows(table))

        case_ids = self.accessor.get_case_ids_in_domain()
        cases = {c.name: c for c in list(self.accessor.get_cases(case_ids))}
        self.assertEqual(cases['Quinton Fortune'].owner_id, dsa_owner._id)
        self.assertTrue(res['errors'])
        error_message = exceptions.InvalidOwnerId.title
        error_col = 'owner_id'
        self.assertEqual(res['errors'][error_message][error_col]['rows'], [2, 3])


def _get_rows(table):
    lines = (line for line in table.split('\n') if line.strip())
    return [[column.strip() for column in row.split('|')] for row in lines]


def make_worksheet_wrapper(*rows):
    return WorksheetWrapper(make_worksheet(rows))


@contextmanager
def restrict_user_to_location(test_case, location):
    orig_user = test_case.couch_user

    role = UserRole.get_or_create_with_permissions(
        domain=test_case.domain,
        name='Regional Case Admin',
        permissions={
            'access_all_locations': False,
            'edit_data': True,
        },
    )
    restricted_user = WebUser.create(None, "restricted_user", "s3cr3t")
    restricted_user.add_domain_membership(test_case.domain, role_id=role._id)
    restricted_user.save()
    restricted_user.set_location(test_case.domain, location)
    test_case.couch_user = restricted_user
    try:
        yield
    finally:
        test_case.couch_user = orig_user
        restricted_user.delete()
        role.delete()


@contextmanager
def make_business_units(domain, shares_cases=True):
    bu = LocationType.objects.create(domain=domain, name='bu', shares_cases=shares_cases)
    dimagi = make_loc('dimagi', 'Dimagi', domain, bu.code)
    inc = make_loc('inc', 'Inc', domain, bu.code, parent=dimagi)
    dsi = make_loc('dsi', 'DSI', domain, bu.code, parent=dimagi)
    dsa = make_loc('dsa', 'DSA', domain, bu.code, parent=dimagi)
    try:
        yield inc, dsi, dsa
    finally:
        for obj in dsa, dsi, inc, dimagi, bu:
            obj.delete()
