import uuid
from contextlib import contextmanager

from django.test import TestCase
from django.utils.dateparse import parse_datetime

from celery import states
from celery.exceptions import Ignore
from mock import patch

from casexml.apps.case.mock import CaseFactory, CaseStructure
from casexml.apps.case.tests.util import delete_all_cases

from corehq.apps.case_importer import exceptions
from corehq.apps.case_importer.do_import import do_import
from corehq.apps.case_importer.tasks import bulk_import_async
from corehq.apps.case_importer.tracking.models import CaseUploadRecord
from corehq.apps.case_importer.util import ImporterConfig, WorksheetWrapper, \
    get_interned_exception
from corehq.apps.commtrack.tests.util import make_loc
from corehq.apps.data_dictionary.tests.utils import setup_data_dictionary
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.groups.models import Group
from corehq.apps.locations.models import LocationType
from corehq.apps.locations.tests.util import restrict_user_by_location
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.test_utils import flag_enabled, flag_disabled
from corehq.util.timezones.conversions import PhoneTime
from corehq.util.workbook_reading import make_worksheet


class ImporterTest(TestCase):

    def setUp(self):
        super(ImporterTest, self).setUp()
        self.domain_obj = create_domain("importer-test")
        self.domain = self.domain_obj.name
        self.default_case_type = 'importer-test-casetype'

        self.couch_user = WebUser.create(None, "test", "foobar", None, None)
        self.couch_user.add_domain_membership(self.domain, is_admin=True)
        self.couch_user.save()

        self.subdomain1 = create_domain('subdomain1')
        self.subdomain2 = create_domain('subdomain2')
        self.ignored_domain = create_domain('ignored-domain')
        create_enterprise_permissions(self.couch_user.username, self.domain,
                                      [self.subdomain1.name, self.subdomain2.name],
                                      [self.ignored_domain.name])

        self.accessor = CaseAccessors(self.domain)

        self.factory = CaseFactory(domain=self.domain, case_defaults={
            'case_type': self.default_case_type,
        })
        delete_all_cases()

    def tearDown(self):
        self.couch_user.delete(self.domain, deleted_by=None)
        self.domain_obj.delete()
        self.subdomain1.delete()
        self.subdomain2.delete()
        self.ignored_domain.delete()
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

    @patch('corehq.apps.case_importer.tasks.bulk_import_async.update_state')
    def testImportFileMissing(self, update_state):
        # by using a made up upload_id, we ensure it's not referencing any real file
        case_upload = CaseUploadRecord(upload_id=str(uuid.uuid4()), task_id=str(uuid.uuid4()))
        case_upload.save()
        res = bulk_import_async.delay(self._config(['anything']), self.domain, case_upload.upload_id)
        self.assertIsInstance(res.result, Ignore)
        update_state.assert_called_with(
            state=states.FAILURE,
            meta=get_interned_exception('Sorry, your session has expired. Please start over and try again.'))
        self.assertEqual(0, len(self.accessor.get_case_ids_in_domain()))

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

    def testCreateCasesWithDuplicateExternalIds(self):
        config = self._config(['case_id', 'age', 'sex', 'location', 'external_id'])
        file = make_worksheet_wrapper(
            ['case_id', 'age', 'sex', 'location', 'external_id'],
            ['case_id-0', 'age-0', 'sex-0', 'location-0', 'external_id-0'],
            ['case_id-1', 'age-1', 'sex-1', 'location-1', 'external_id-0'],
            ['case_id-2', 'age-2', 'sex-2', 'location-2', 'external_id-1'],
        )
        res = do_import(file, config, self.domain)
        self.assertEqual(3, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertFalse(res['errors'])
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertItemsEqual(
            [case.external_id for case in self.accessor.get_cases(case_ids)],
            ['external_id-0', 'external_id-0', 'external_id-1']
        )

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
        self.assertEqual(0, len(self.accessor.get_case_ids_in_domain()))

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
        self.assertEqual(0, len(self.accessor.get_case_ids_in_domain()))

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
        self.assertEqual(5, len(self.accessor.get_case_ids_in_domain()))

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
        self.assertEqual(2, res['num_chunks'])  # the lookup causes an extra chunk

        # should just create the one case
        case_ids = self.accessor.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        [case] = self.accessor.get_cases(case_ids)
        self.assertEqual(external_id, case.external_id)
        for prop in ['age', 'sex', 'location']:
            self.assertTrue(prop in case.get_case_property(prop))

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

        # Should successfully match on `rows` cases
        res = do_import(file, config, self.domain)
        self.assertEqual(rows, res['created_count'])
        # Should create child cases
        self.assertEqual(len(self.accessor.get_reverse_indexed_cases([parent_case.case_id])), 3)
        self.assertEqual(self.accessor.get_extension_case_ids([parent_case.case_id]), [])

        file_missing = make_worksheet_wrapper(
            ['parent_id', 'name', 'case_id'],
            ['parent_id-0', 'name-0', 'case_id-0'],
            ['parent_id-1', 'name-1', 'case_id-1'],
            ['parent_id-2', 'name-2', 'case_id-2'],
        )

        # Should be unable to find parent case on `rows` cases
        res = do_import(file_missing, config, self.domain)
        error_column_name = 'parent_id'
        self.assertEqual(rows,
                         len(res['errors'][exceptions.InvalidParentId.title][error_column_name]['rows']),
                         "All cases should have missing parent")

    def testExtensionCase(self):
        headers = ['parent_id', 'name', 'case_id', 'parent_relationship_type', 'parent_identifier']
        config = self._config(headers, create_new_cases=True, search_column='case_id')
        [parent_case] = self.factory.create_or_update_case(CaseStructure(attrs={'create': True}))
        self.assertEqual(1, len(self.accessor.get_case_ids_in_domain()))

        file = make_worksheet_wrapper(
            headers,
            [parent_case.case_id, 'name-0', 'case_id-0', 'extension', 'host'],
            [parent_case.case_id, 'name-1', 'case_id-1', 'extension', 'mother'],
            [parent_case.case_id, 'name-2', 'case_id-2', 'child', 'parent'],
        )

        # Should successfully match on `rows` cases
        res = do_import(file, config, self.domain)
        self.assertEqual(res['created_count'], 3)
        # Of the 3, 2 should be extension cases
        extension_case_ids = self.accessor.get_extension_case_ids([parent_case.case_id])
        self.assertEqual(len(extension_case_ids), 2)
        extension_cases = self.accessor.get_cases(extension_case_ids)
        # Check that identifier is set correctly
        self.assertEqual(
            {'host', 'mother'},
            {
                c.indices[0].identifier
                for c in extension_cases
            }
        )

    @flag_enabled('DOMAIN_PERMISSIONS_MIRROR')
    def test_multiple_domain_case_import(self):
        headers_with_domain = ['case_id', 'name', 'artist', 'domain']
        config_1 = self._config(headers_with_domain, create_new_cases=True, search_column='case_id')
        case_with_domain_file = make_worksheet_wrapper(
            ['case_id', 'name', 'artist', 'domain'],
            ['', 'name-0', 'artist-0', self.domain],
            ['', 'name-1', 'artist-1', self.subdomain1.name],
            ['', 'name-2', 'artist-2', self.subdomain2.name],
            ['', 'name-3', 'artist-3', self.domain],
            ['', 'name-4', 'artist-4', self.domain],
            ['', 'name-5', 'artist-5', 'not-existing-domain'],
            ['', 'name-6', 'artist-6', self.ignored_domain.name],
        )
        res = do_import(case_with_domain_file, config_1, self.domain)
        self.assertEqual(5, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(2, res['failed_count'])

        # Asserting current domain
        cur_case_ids = self.accessor.get_case_ids_in_domain()
        cur_cases = list(self.accessor.get_cases(cur_case_ids))
        self.assertEqual(3, len(cur_cases))
        #Asserting current domain case property
        cases = {c.name: c for c in cur_cases}
        self.assertEqual(cases['name-0'].get_case_property('artist'), 'artist-0')

        # Asserting subdomain 1
        s1_case_ids = CaseAccessors(self.subdomain1.name).get_case_ids_in_domain()
        s1_cases = list(self.accessor.get_cases(s1_case_ids))
        self.assertEqual(1, len(s1_cases))
        # Asserting subdomain 1 case property
        s1_cases_pro = {c.name: c for c in s1_cases}
        self.assertEqual(s1_cases_pro['name-1'].get_case_property('artist'), 'artist-1')

        # Asserting subdomain 2
        s2_case_ids = CaseAccessors(self.subdomain2.name).get_case_ids_in_domain()
        s2_cases = list(self.accessor.get_cases(s2_case_ids))
        self.assertEqual(1, len(s2_cases))
        # Asserting subdomain 2 case property
        s2_cases_pro = {c.name: c for c in s2_cases}
        self.assertEqual(s2_cases_pro['name-2'].get_case_property('artist'), 'artist-2')

    @flag_disabled('DOMAIN_PERMISSIONS_MIRROR')
    def test_multiple_domain_case_import_mirror_domain_disabled(self):
        headers_with_domain = ['case_id', 'name', 'artist', 'domain']
        config_1 = self._config(headers_with_domain, create_new_cases=True, search_column='case_id')
        case_with_domain_file = make_worksheet_wrapper(
            ['case_id', 'name', 'artist', 'domain'],
            ['', 'name-0', 'artist-0', self.domain],
            ['', 'name-1', 'artist-1', 'domain-1'],
            ['', 'name-2', 'artist-2', 'domain-2'],
            ['', 'name-3', 'artist-3', self.domain],
            ['', 'name-4', 'artist-4', self.domain],
            ['', 'name-5', 'artist-5', 'not-existing-domain']
        )
        res = do_import(case_with_domain_file, config_1, self.domain)
        self.assertEqual(6, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, res['failed_count'])
        case_ids = self.accessor.get_case_ids_in_domain()
        # Asserting current domain
        cur_cases = list(self.accessor.get_cases(case_ids))
        self.assertEqual(6, len(cur_cases))
        #Asserting domain case property
        cases = {c.name: c for c in cur_cases}
        self.assertEqual(cases['name-0'].get_case_property('domain'), self.domain)

    def import_mock_file(self, rows):
        config = self._config(rows[0])
        xls_file = make_worksheet_wrapper(*rows)
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
        location = make_loc('loc-1', 'Loc 1', self.domain, case_sharing.code)
        make_loc('loc-2', 'Loc 2', self.domain, case_sharing.code)
        duplicate_loc = make_loc('loc-3', 'Loc 2', self.domain, case_sharing.code)
        improper_loc = make_loc('loc-4', 'Loc 4', self.domain, non_case_sharing.code)

        res = self.import_mock_file([
            ['case_id', 'name', 'owner_id', 'owner_name'],
            ['', 'location-owner-id', location.location_id, ''],
            ['', 'location-owner-code', '', location.site_code],
            ['', 'location-owner-name', '', location.name],
            ['', 'duplicate-location-name', '', duplicate_loc.name],
            ['', 'non-case-owning-name', '', improper_loc.name],
        ])
        case_ids = self.accessor.get_case_ids_in_domain()
        cases = {c.name: c for c in list(self.accessor.get_cases(case_ids))}

        self.assertEqual(cases['location-owner-id'].owner_id, location.location_id)
        self.assertEqual(cases['location-owner-code'].owner_id, location.location_id)
        self.assertEqual(cases['location-owner-name'].owner_id, location.location_id)

        error_message = exceptions.DuplicateLocationName.title
        error_column_name = None
        self.assertIn(error_message, res['errors'])
        self.assertEqual(res['errors'][error_message][error_column_name]['rows'], [5])

        error_message = exceptions.InvalidOwner.title
        self.assertIn(error_message, res['errors'])
        error_column_name = 'owner_name'
        self.assertEqual(res['errors'][error_message][error_column_name]['rows'], [6])

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

    def test_date_validity_checking(self):
        setup_data_dictionary(self.domain, self.default_case_type, [('d1', 'date'), ('d2', 'date')])
        file_rows = [
            ['case_id', 'd1', 'd2'],
            ['', '2011-04-16', ''],
            ['', '2011-44-22', '2021-03-44'],
        ]

        # With validity checking enabled, the two bad dates on row 3
        # should casue that row to fail to import, and both should be
        # flagged as invalid dates in the error report. (The blank date
        # on row 2 "passes" validity checking, there is currently not
        # a way to indicate whether a field is required or not so it's
        # assumed not required.)
        with flag_enabled('CASE_IMPORT_DATA_DICTIONARY_VALIDATION'):
            res = self.import_mock_file(file_rows)
        self.assertEqual(1, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(1, res['failed_count'])
        self.assertTrue(res['errors'])
        error_message = exceptions.InvalidDate.title
        error_cols = ['d1', 'd2']
        for col in error_cols:
            self.assertEqual(res['errors'][error_message][col]['rows'], [3])

        # Without the flag enabled, all the rows should be imported.
        res = self.import_mock_file(file_rows)
        self.assertEqual(2, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, res['failed_count'])
        self.assertFalse(res['errors'])

    def test_select_validity_checking(self):
        setup_data_dictionary(self.domain, self.default_case_type,
                              [('mc', 'select'), ('d1', 'date')], {'mc': ['True', 'False']})
        file_rows = [
            ['case_id', 'd1', 'mc'],
            ['', '2022-04-01', 'True'],
            ['', '1965-03-30', 'false'],
            ['', '1944-06-15', ''],
        ]

        # With validity checking enabled, the bad choice on row 3
        # should case that row to fail to import and should be
        # flagged as invalid. The blank one should be valid.
        with flag_enabled('CASE_IMPORT_DATA_DICTIONARY_VALIDATION'):
            res = self.import_mock_file(file_rows)
        self.assertEqual(2, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(1, res['failed_count'])
        self.assertTrue(res['errors'])
        error_message = exceptions.InvalidSelectValue.title
        self.assertEqual(res['errors'][error_message]['mc']['rows'], [3])

        # Without the flag enabled, all the rows should be imported.
        res = self.import_mock_file(file_rows)
        self.assertEqual(3, res['created_count'])
        self.assertEqual(0, res['match_count'])
        self.assertEqual(0, res['failed_count'])
        self.assertFalse(res['errors'])

    def test_columns_and_rows_align(self):
        with get_commcare_user(self.domain) as case_owner:
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
                restrict_user_to_location(self.domain, self, dsa):
            res = self.import_mock_file([
                ['case_id', 'name', 'owner_id'],
                ['', 'Leonard Nimoy', inc.location_id],
                ['', 'Kapil Dev', dsi.location_id],
                ['', 'Quinton Fortune', dsa.location_id],
            ])

        case_ids = self.accessor.get_case_ids_in_domain()
        cases = {c.name: c for c in list(self.accessor.get_cases(case_ids))}
        self.assertEqual(cases['Quinton Fortune'].owner_id, dsa.location_id)
        self.assertTrue(res['errors'])
        error_message = exceptions.InvalidLocation.title
        error_col = 'owner_id'
        self.assertEqual(res['errors'][error_message][error_col]['rows'], [2, 3])

    def test_user_can_access_owner(self):
        with make_business_units(self.domain) as (inc, dsi, dsa), \
                restrict_user_to_location(self.domain, self, dsa):
            inc_owner = CommCareUser.create(self.domain, 'inc', 'pw', None, None, location=inc)
            dsi_owner = CommCareUser.create(self.domain, 'dsi', 'pw', None, None, location=dsi)
            dsa_owner = CommCareUser.create(self.domain, 'dsa', 'pw', None, None, location=dsa)

            res = self.import_mock_file([
                ['case_id', 'name', 'owner_id'],
                ['', 'Leonard Nimoy', inc_owner._id],
                ['', 'Kapil Dev', dsi_owner._id],
                ['', 'Quinton Fortune', dsa_owner._id],
            ])

        case_ids = self.accessor.get_case_ids_in_domain()
        cases = {c.name: c for c in list(self.accessor.get_cases(case_ids))}
        self.assertEqual(cases['Quinton Fortune'].owner_id, dsa_owner._id)
        self.assertTrue(res['errors'])
        error_message = exceptions.InvalidLocation.title
        error_col = 'owner_id'
        self.assertEqual(res['errors'][error_message][error_col]['rows'], [2, 3])

    def test_bad_owner_proper_column_name(self):
        bad_group = Group(
            domain=self.domain,
            name="non_case_sharing_group",
            case_sharing=False,
        )
        bad_group.save()
        self.addCleanup(bad_group.delete)
        res = self.import_mock_file([
            ['case_id', 'name', '', 'favorite_color', 'owner_name'],
            ['', 'Jeff', '', 'blue', bad_group.name],
        ])
        self.assertIn(exceptions.InvalidOwner.title, res['errors'])

    def test_case_name_too_long(self):
        res = self.import_mock_file([
            ['case_id', 'name', 'external_id', 'favorite_color'],
            ['', 'normal name', '', 'blue'],
            ['', 'A' * 300, '', 'polka dot'],
            ['', 'another normal name', 'A' * 300, 'polka dot'],
        ])
        self.assertEqual(1, res['created_count'])
        self.assertEqual(2, res['failed_count'])
        self.assertIn(exceptions.CaseNameTooLong.title, res['errors'])
        self.assertIn(exceptions.ExternalIdTooLong.title, res['errors'])


def make_worksheet_wrapper(*rows):
    return WorksheetWrapper(make_worksheet(rows))


@contextmanager
def restrict_user_to_location(domain, test_case, location):
    orig_user = test_case.couch_user

    restricted_user = WebUser.create(test_case.domain, "restricted", "s3cr3t", None, None)
    restricted_user.set_location(test_case.domain, location)
    restrict_user_by_location(test_case.domain, restricted_user)
    test_case.couch_user = restricted_user
    try:
        yield
    finally:
        test_case.couch_user = orig_user
        restricted_user.delete(domain, deleted_by=None)


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


@contextmanager
def get_commcare_user(domain_name):
    user = CommCareUser.create(domain_name, 'username', 'pw', None, None)
    try:
        yield user
    finally:
        user.delete(domain_name, deleted_by=None)
