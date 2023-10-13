import uuid
from unittest.mock import patch, MagicMock

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.util.test_utils import (
    disable_quickcache,
    flag_enabled,
    privilege_enabled,
)

from ..utils import submit_case_blocks


@sharded
@disable_quickcache
@privilege_enabled(privileges.API_ACCESS)
@flag_enabled('CASE_API_V0_6')
@flag_enabled('API_THROTTLE_WHITELIST')
@patch('corehq.apps.hqcase.api.updates.validate_update_permission', MagicMock())
class TestCaseAPI(TestCase):
    domain = 'test-update-cases'
    maxDiff = None

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        role = UserRole.create(
            cls.domain, 'edit-data', permissions=HqPermissions(edit_data=True, access_api=True)
        )
        cls.web_user = WebUser.create(cls.domain, 'netflix', 'password', None, None, role_id=role.get_id)

    def setUp(self):
        self.client.login(username='netflix', password='password')

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)
        FormProcessorTestUtils.delete_all_xforms(self.domain)

    @classmethod
    def tearDownClass(cls):
        cls.web_user.delete(cls.domain, deleted_by=None)
        cls.domain_obj.delete()
        super().tearDownClass()

    def _make_case(self, parent_id=None):
        xform, cases = submit_case_blocks([CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='player',
            case_name='Elizabeth Harmon',
            external_id='1',
            owner_id='methuen_home',
            create=True,
            update={
                'sport': 'chess',
                'rank': '1600',
                'dob': '1948-11-02',
            },
            index={
                'parent': IndexAttrs('player', parent_id, 'child'),
            } if parent_id else None,
        ).as_text()], domain=self.domain)
        return cases[0]

    def _create_case(self, body):
        return self.client.post(
            reverse('case_api', args=(self.domain,)),
            body,
            content_type="application/json;charset=utf-8",
            HTTP_USER_AGENT="user agent string",
        )

    def _update_case(self, case_id, body):
        return self.client.put(
            reverse('case_api', args=(self.domain, case_id,)),
            body,
            content_type="application/json;charset=utf-8",
            HTTP_USER_AGENT="user agent string",
        )

    def _bulk_update_cases(self, body):
        # for the time being, the implementation is the same
        return self._create_case(body)

    def test_basic_get_list(self):
        with patch('corehq.apps.hqcase.views.get_list', lambda *args: {'example': 'result'}):
            res = self.client.get(reverse('case_api', args=(self.domain,)))
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {'example': 'result'})

    def test_create_case(self):
        res = self._create_case({
            # notable exclusions: case_id, date_opened, date_modified
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'external_id': '1',
            'owner_id': 'methuen_home',
            'properties': {
                'sport': 'chess',
                'dob': '1948-11-02',
            },
        }).json()
        self.assertItemsEqual(res.keys(), ['case', 'form_id'])
        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        self.assertEqual(case.domain, self.domain)
        self.assertEqual(case.type, 'player')
        self.assertFalse(case.closed)
        self.assertEqual(case.name, 'Elizabeth Harmon')
        self.assertEqual(case.external_id, '1')
        self.assertEqual(case.owner_id, 'methuen_home')
        self.assertEqual(case.opened_by, self.web_user.user_id)
        self.assertEqual(case.dynamic_case_properties(), {
            'dob': '1948-11-02',
            'sport': 'chess',
        })

        xform = XFormInstance.objects.get_form(res['form_id'])
        self.assertEqual(xform.xmlns, 'http://commcarehq.org/case_api')
        self.assertEqual(xform.metadata.userID, self.web_user.user_id)
        self.assertEqual(xform.metadata.deviceID, 'user agent string')

    def test_non_schema_updates(self):
        res = self._create_case({
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'external_id': '1',
            'owner_id': 'methuen_home',
            'bad_property': "this doesn't fit the schema!",
            'properties': {'sport': 'chess'},
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error'], "'bad_property' is not a valid field.")

    def test_empty_case_type(self):
        res = self._create_case({
            'case_type': '',
            'case_name': 'Elizabeth Harmon',
            'owner_id': 'methuen_home',
        }).json()
        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        self.assertEqual(case.name, 'Elizabeth Harmon')
        self.assertEqual(case.type, '')

    def test_no_required_updates(self):
        case = self._make_case()

        res = self._update_case(case.case_id, {
            'properties': {'rank': '2100'}
        })
        self.assertEqual(res.status_code, 200)

        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        # Nothing was zeroed out by being omitted
        self.assertEqual(case.name, 'Elizabeth Harmon')
        self.assertEqual(case.owner_id, 'methuen_home')
        self.assertEqual(case.dynamic_case_properties(), {
            'dob': '1948-11-02',
            'rank': '2100',
            'sport': 'chess',
        })

    def test_update_case(self):
        case = self._make_case()

        res = self._update_case(case.case_id, {
            # notable exclusions: case_id, date_opened, date_modified, case_type
            'case_name': 'Beth Harmon',
            'owner_id': 'us_chess_federation',
            'properties': {
                'rank': '2100',
                'champion': 'true',
            },
        }).json()
        self.assertItemsEqual(res.keys(), ['case', 'form_id'])

        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertFalse(case.closed)
        self.assertEqual(case.name, 'Beth Harmon')
        self.assertEqual(case.owner_id, 'us_chess_federation')
        self.assertEqual(case.dynamic_case_properties(), {
            'champion': 'true',
            'dob': '1948-11-02',
            'rank': '2100',
            'sport': 'chess',
        })

    def test_can_update_case_type(self):
        case = self._make_case()
        res = self._update_case(case.case_id, {
            'case_name': 'Beth Harmon',
            'case_type': 'legend',
        })
        self.assertEqual(res.status_code, 200)
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertEqual(case.type, 'legend')

    def test_close_case(self):
        case = self._make_case()
        res = self._update_case(case.case_id, {'close': True})
        self.assertEqual(res.status_code, 200)
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertTrue(case.closed)

    def test_create_closed_case(self):
        res = self._create_case({
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'owner_id': 'us_chess_federation',
            'close': True,
        })
        self.assertEqual(res.status_code, 200)
        case_id = res.json()['case']['case_id']
        case = CommCareCase.objects.get_case(case_id, self.domain)
        self.assertTrue(case.closed)

    def test_update_case_bad_id(self):
        res = self._update_case('notarealcaseid', {
            'case_name': 'Beth Harmon',
            'owner_id': 'us_chess_federation',
            'properties': {
                'rank': '2100',
                'champion': 'true',
            },
        })
        self.assertEqual(res.json()['error'], "No case found with ID 'notarealcaseid'")
        self.assertEqual(CommCareCase.objects.get_case_ids_in_domain(self.domain), [])

    def test_update_case_on_other_domain(self):
        case_id = str(uuid.uuid4())
        submit_case_blocks([CaseBlock(
            case_id=case_id,
            case_type='player',
            case_name='Judit Polgár',
            create=True,
            update={}
        ).as_text()], domain='other_domain')

        res = self._update_case(case_id, {
            'owner_id': 'stealing_this_case',
        })
        self.assertEqual(res.json()['error'], f"No case found with ID '{case_id}'")
        self.assertEqual(CommCareCase.objects.get_case_ids_in_domain(self.domain), [])

    def test_create_child_case(self):
        parent_case = self._make_case()
        res = self._create_case({
            'case_type': 'match',
            'case_name': 'Harmon/Luchenko',
            'external_id': '23',
            'owner_id': 'harmon',
            'properties': {
                'winner': 'Harmon',
            },
            'indices': {
                'parent': {
                    'case_id': parent_case.case_id,
                    'case_type': 'player',
                    'relationship': 'child',
                },
            },
        }).json()
        self.assertItemsEqual(res.keys(), ['case', 'form_id'])

        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        self.assertEqual(case.name, 'Harmon/Luchenko')
        self.assertEqual(case.external_id, '23')
        self.assertEqual(case.owner_id, 'harmon')
        self.assertEqual(case.dynamic_case_properties(), {'winner': 'Harmon'})
        self.assertEqual(case.indices[0].identifier, 'parent')
        self.assertEqual(case.indices[0].referenced_id, parent_case.case_id)
        self.assertEqual(case.indices[0].referenced_type, 'player')
        self.assertEqual(case.indices[0].relationship, 'child')
        self.assertEqual(case.indices[0].referenced_case.case_id, parent_case.case_id)

    def test_set_parent_by_external_id(self):
        parent_case = self._make_case()
        res = self._create_case({
            'case_type': 'match',
            'case_name': 'Harmon/Luchenko',
            'owner_id': 'harmon',
            'indices': {
                'parent': {
                    'external_id': parent_case.external_id,
                    'case_type': 'player',
                    'relationship': 'child',
                },
            },
        }).json()
        self.assertItemsEqual(res.keys(), ['case', 'form_id'])

        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        self.assertEqual(case.indices[0].referenced_id, parent_case.case_id)

    def test_set_parent_by_bad_external_id(self):
        parent_case = self._make_case()
        res = self._create_case({
            'case_type': 'match',
            'case_name': 'Harmon/Luchenko',
            'owner_id': 'harmon',
            'indices': {
                'parent': {
                    'external_id': 'MISSING',
                    'case_type': 'player',
                    'relationship': 'child',
                },
            },
        }).json()
        self.assertEqual(res['error'], "Could not find a case with external_id 'MISSING'")

    def test_set_parent_missing_field(self):
        parent_case = self._make_case()
        res = self._create_case({
            'case_type': 'match',
            'case_name': 'Harmon/Luchenko',
            'owner_id': 'harmon',
            'indices': {
                'parent': {
                    'external_id': parent_case.external_id,
                    'case_type': 'player',
                    # 'relationship' is not specified
                },
            },
        }).json()
        self.assertEqual(res['error'], "Property relationship is required when creating or updating case indices")

    def test_delete_index(self):
        # aka remove child case
        parent_case = self._make_case()
        child_case = self._make_case(parent_id=parent_case.case_id)
        self.assertEqual([c.case_id for c in parent_case.get_subcases()],
                         [child_case.case_id])

        res = self._update_case(child_case.case_id, {
            'indices': {
                'parent': {
                    'case_id': '',
                    'case_type': 'player',
                    'relationship': 'child',
                },
            },
        })
        self.assertEqual(res.status_code, 200)

        parent_case = CommCareCase.objects.get_case(parent_case.case_id, self.domain)
        self.assertEqual(parent_case.get_subcases(), [])

        child_case = CommCareCase.objects.get_case(child_case.case_id, self.domain)
        self.assertEqual(child_case.get_index('parent').referenced_id, '')

    def test_bulk_action(self):
        existing_case = self._make_case()
        res = self._bulk_update_cases([
            {
                'create': False,
                'case_id': existing_case.case_id,
                'case_name': 'Beth Harmon',
                'owner_id': 'us_chess_federation',
                'properties': {
                    'rank': '2100',
                    'champion': 'true',
                },
            },
            {
                'create': True,
                'case_type': 'player',
                'case_name': 'Jolene',
                'external_id': 'jolene',
                'owner_id': 'methuen_home',
                'properties': {
                    'sport': 'squash',
                    'dob': '1947-03-09',
                },
            },
        ]).json()
        #  only returns a single form ID - chunking should happen in the client
        self.assertItemsEqual(res.keys(), ['cases', 'form_id'])

        updated_case = CommCareCase.objects.get_case(existing_case.case_id, self.domain)
        self.assertEqual(updated_case.name, 'Beth Harmon')

        new_case = CommCareCase.objects.get_case_by_external_id(self.domain, 'jolene')
        self.assertEqual(new_case.name, 'Jolene')

    def test_bulk_without_create_flag(self):
        res = self._bulk_update_cases([{
            # valid except it needs 'create' specified
            'case_type': 'player',
            'case_name': 'Jolene',
            'owner_id': 'methuen_home',
        }])
        self.assertEqual(res.status_code, 400)
        self.assertIn("A 'create' flag is required for each update.",
                      res.json()['error'])

    def test_attempt_create_with_case_id(self):
        res = self._bulk_update_cases([{
            'create': True,
            'case_type': 'player',
            'case_name': 'Jolene',
            'owner_id': 'methuen_home',
            'case_id': 'somethingmalicious',
        }])
        self.assertEqual(res.status_code, 400)
        self.assertIn("You cannot specify case_id when creating a new case",
                      res.json()['error'])

    def test_bulk_update_too_big(self):
        res = self._bulk_update_cases([
            {'create': True, 'case_name': f'case {i}', 'case_type': 'player'}
            for i in range(103)
        ])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(
            res.json(),
            {'error': "You cannot submit more than 100 updates in a single request"}
        )

    def test_update_with_bad_case_id(self):
        res = self._bulk_update_cases([
            {
                # attempt to update existing case, but it doesn't exist
                'create': False,
                'case_id': 'notarealcaseid',
                'case_name': 'Beth Harmon',
                'owner_id': 'us_chess_federation',
            },
            {
                # Also have a (valid) case creation, though it shouldn't go through
                'create': True,
                'case_type': 'player',
                'case_name': 'Jolene',
                'owner_id': 'methuen_home',
            },
        ])
        self.assertEqual(res.json()['error'], "No case found with ID 'notarealcaseid'")
        self.assertEqual(CommCareCase.objects.get_case_ids_in_domain(self.domain), [])

    def test_create_parent_and_child_together(self):
        res = self._bulk_update_cases([
            {
                'create': True,
                'case_type': 'player',
                'case_name': 'Elizabeth Harmon',
                'owner_id': 'us_chess_federation',
                'external_id': 'beth',
                'temporary_id': 'beth_harmon',
            },
            {
                'create': True,
                'case_type': 'match',
                'case_name': 'Harmon/Luchenko',
                'owner_id': 'harmon',
                'external_id': 'harmon-luchenko',
                'properties': {
                    'winner': 'Harmon',
                },
                'indices': {
                    'parent': {
                        # case_id is unknown at this point
                        'temporary_id': 'beth_harmon',
                        'case_type': 'player',
                        'relationship': 'child',
                    },
                },
            },
        ])
        self.assertEqual(res.status_code, 200)
        parent = CommCareCase.objects.get_case_by_external_id(self.domain, 'beth')
        child = CommCareCase.objects.get_case_by_external_id(self.domain, 'harmon-luchenko')
        self.assertEqual(parent.case_id, child.get_index('parent').referenced_id)

    def test_create_child_with_no_parent(self):
        res = self._bulk_update_cases([
            {
                'create': True,
                'case_type': 'match',
                'case_name': 'Harmon/Luchenko',
                'owner_id': 'harmon',
                'external_id': 'harmon-luchenko',
                'properties': {
                    'winner': 'Harmon',
                },
                'indices': {
                    'parent': {
                        'temporary_id': 'MISSING',
                        'case_type': 'player',
                        'relationship': 'child',
                    },
                },
            },
        ])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error'], "Could not find a case with temporary_id 'MISSING'")

    def test_index_reference_to_uncreated_external_id(self):
        res = self._bulk_update_cases([
            {
                'create': True,
                'case_type': 'player',
                'case_name': 'Elizabeth Harmon',
                'owner_id': 'us_chess_federation',
                'external_id': 'beth',
            },
            {
                'create': True,
                'case_type': 'match',
                'case_name': 'Harmon/Luchenko',
                'external_id': 'harmon-luchenko',
                'owner_id': 'harmon',
                'indices': {
                    'parent': {
                        # This case will be created in the same payload
                        'external_id': 'beth',
                        'case_type': 'player',
                        'relationship': 'child',
                    },
                },
            },
        ])
        self.assertEqual(res.status_code, 200)
        parent = CommCareCase.objects.get_case_by_external_id(self.domain, 'beth')
        child = CommCareCase.objects.get_case_by_external_id(self.domain, 'harmon-luchenko')
        self.assertEqual(parent.case_id, child.get_index('parent').referenced_id)

    def test_update_by_external_id(self):
        case = self._make_case()
        res = self.client.put(
            reverse('case_api', args=(self.domain,)),
            {
                'external_id': case.external_id,
                'properties': {'champion': 'true'},
            },
            content_type="application/json;charset=utf-8",
        )
        self.assertEqual(res.status_code, 200)
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertEqual(case.dynamic_case_properties().get('champion'), 'true')

    def test_update_by_external_id_doesnt_exist(self):
        res = self.client.put(
            reverse('case_api', args=(self.domain,)),
            {
                'external_id': 'notarealcaseid',
                'properties': {'champion': 'true'},
            },
            content_type="application/json;charset=utf-8",
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error'], "Could not find a case with external_id 'notarealcaseid'")

    def test_bulk_update_by_external_id(self):
        case = self._make_case()
        res = self._bulk_update_cases([{
            'create': False,
            'external_id': case.external_id,
            'owner_id': 'us_chess_federation',
        }])
        self.assertEqual(res.status_code, 200)
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertEqual(case.owner_id, 'us_chess_federation')

    def test_bulk_update_external_id_doesnt_exist(self):
        res = self._bulk_update_cases([{
            'create': False,
            'external_id': 'notarealcaseid',
            'owner_id': 'us_chess_federation',
        }])
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json()['error'], "Could not find a case with external_id 'notarealcaseid'")

    def test_non_json_data(self):
        res = self._create_case("this isn't json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {'error': "Payload must be valid JSON"})

    def test_missing_required_field(self):
        res = self._create_case({
            # case_name is not provided!
            'case_type': 'player',
            'owner_id': 'methuen_home',
            'properties': {'dob': '1948-11-02'},
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {'error': "Property case_name is required."})

    def test_invalid_properties(self):
        res = self._create_case({
            'case_name': 'Beth Harmon',
            'case_type': 'player',
            'owner_id': 'methuen_home',
            'properties': {
                'dob': '1948-11-02',
                'age': 72,  # Can't pass integers
            },
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {
            'error': "Error with case property 'age'. Values must be strings, received '72'"
        })

    def test_non_xml_properties(self):
        res = self._create_case({
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'owner_id': 'methuen_home',
            'properties': {'not good': 'tsk tsk'},
        })
        self.assertEqual(res.status_code, 400)
        msg = "Error with case property 'not good'. Case property names must be valid XML identifiers."
        self.assertEqual(res.json()['error'], msg)

    def test_non_xml_index_name(self):
        parent_case = self._make_case()
        res = self._create_case({
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'owner_id': 'methuen_home',
            'indices': {
                "Robert'); DROP TABLE students;--": {
                    'case_id': parent_case.case_id,
                    'case_type': 'player',
                    'relationship': 'child',
                },
            },
        })
        self.assertEqual(res.status_code, 400)
        msg = ("Error with index 'Robert'); DROP TABLE students;--'. "
               "Index names must be valid XML identifiers.")
        self.assertEqual(res.json()['error'], msg)


    def test_bad_index_reference(self):
        res = self._create_case({
            'case_type': 'match',
            'case_name': 'Harmon/Luchenko',
            'external_id': '23',
            'owner_id': 'harmon',
            'properties': {
                'dob': '1948-11-02',
            },
            'indices': {
                'parent': {
                    'case_id': 'bad404bad',  # This doesn't exist
                    'case_type': 'player',
                    'relationship': 'child',
                },
            },
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("InvalidCaseIndex", res.json()['error'])
        form = XFormInstance.objects.get_form(res.json()['form_id'])
        self.assertEqual(form.is_error, True)

    def test_unset_external_id(self):
        case = self._make_case()
        self.assertEqual(case.external_id, '1')

        res = self._update_case(case.case_id, {
            'external_id': '',
        })
        self.assertEqual(res.status_code, 200)
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertEqual(case.external_id, '')

    def test_omitting_external_id_doesnt_clear_it(self):
        case = self._make_case()
        self.assertEqual(case.external_id, '1')

        res = self._update_case(case.case_id, {
            'properties': {'champion': 'true'},
        })
        self.assertEqual(res.status_code, 200)
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        self.assertEqual(case.external_id, '1')


    def test_urls_without_trailing_slash(self):
        case_id = self._make_case().case_id
        urls = [
            (self.client.post, reverse('case_api', args=(self.domain,)).rstrip("/")),
            (self.client.put, reverse('case_api', args=(self.domain, case_id)).rstrip("/")),
        ]
        for request_fn, url in urls:
            res = request_fn(
                url,
                {'body': 'bad case update format'},
                content_type="application/json;charset=utf-8",
                HTTP_USER_AGENT="user agent string",
            )
            # These requests should return a 400 because of the bad body, not a 301 redirect
            self.assertEqual(res.status_code, 400)
