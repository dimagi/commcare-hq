import json
import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.tests.utils import FormProcessorTestUtils, sharded
from corehq.util.test_utils import (
    disable_quickcache,
    flag_enabled,
    privilege_enabled,
)

from ..utils import submit_case_blocks


@es_test(requires=[case_search_adapter], setup_class=True)
@sharded
@disable_quickcache
@privilege_enabled(privileges.API_ACCESS)
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
            reverse('case_api_detail', args=(self.domain, case_id,)),
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
        assert res.status_code == 200
        assert res.json() == {'example': 'result'}

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
        assert set(res.keys()) == set(['case', 'form_id'])
        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        assert case.domain == self.domain
        assert case.type == 'player'
        assert not case.closed
        assert case.name == 'Elizabeth Harmon'
        assert case.external_id == '1'
        assert case.owner_id == 'methuen_home'
        assert case.opened_by == self.web_user.user_id
        assert case.dynamic_case_properties() == {
            'dob': '1948-11-02',
            'sport': 'chess',
        }

        xform = XFormInstance.objects.get_form(res['form_id'])
        assert xform.xmlns == 'http://commcarehq.org/case_api'
        assert xform.metadata.userID == self.web_user.user_id
        assert xform.metadata.deviceID == 'user agent string'

    def test_non_schema_updates(self):
        res = self._create_case({
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'external_id': '1',
            'owner_id': 'methuen_home',
            'bad_property': "this doesn't fit the schema!",
            'properties': {'sport': 'chess'},
        })
        assert res.status_code == 400
        assert res.json()['error'] == "'bad_property' is not a valid field."

    def test_empty_case_type(self):
        res = self._create_case({
            'case_type': '',
            'case_name': 'Elizabeth Harmon',
            'owner_id': 'methuen_home',
        }).json()
        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        assert case.name == 'Elizabeth Harmon'
        assert case.type == ''

    def test_no_required_updates(self):
        case = self._make_case()

        res = self._update_case(case.case_id, {
            'properties': {'rank': '2100'}
        })
        assert res.status_code == 200

        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        # Nothing was zeroed out by being omitted
        assert case.name == 'Elizabeth Harmon'
        assert case.owner_id == 'methuen_home'
        assert case.dynamic_case_properties() == {
            'dob': '1948-11-02',
            'rank': '2100',
            'sport': 'chess',
        }

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
        assert set(res.keys()) == set(['case', 'form_id'])

        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        assert not case.closed
        assert case.name == 'Beth Harmon'
        assert case.owner_id == 'us_chess_federation'
        assert case.dynamic_case_properties() == {
            'champion': 'true',
            'dob': '1948-11-02',
            'rank': '2100',
            'sport': 'chess',
        }

    def test_can_update_case_type(self):
        case = self._make_case()
        res = self._update_case(case.case_id, {
            'case_name': 'Beth Harmon',
            'case_type': 'legend',
        })
        assert res.status_code == 200
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        assert case.type == 'legend'

    def test_close_case(self):
        case = self._make_case()
        res = self._update_case(case.case_id, {'close': True})
        assert res.status_code == 200
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        assert case.closed

    def test_create_closed_case(self):
        res = self._create_case({
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'owner_id': 'us_chess_federation',
            'close': True,
        })
        assert res.status_code == 200
        case_id = res.json()['case']['case_id']
        case = CommCareCase.objects.get_case(case_id, self.domain)
        assert case.closed

    def test_update_case_bad_id(self):
        res = self._update_case('notarealcaseid', {
            'case_name': 'Beth Harmon',
            'owner_id': 'us_chess_federation',
            'properties': {
                'rank': '2100',
                'champion': 'true',
            },
        })
        assert res.json()['error'] == "No case found with ID 'notarealcaseid'"
        assert CommCareCase.objects.get_case_ids_in_domain(self.domain) == []

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
        assert res.json()['error'] == f"No case found with ID '{case_id}'"
        assert CommCareCase.objects.get_case_ids_in_domain(self.domain) == []

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
        assert set(res.keys()) == set(['case', 'form_id'])

        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        assert case.name == 'Harmon/Luchenko'
        assert case.external_id == '23'
        assert case.owner_id == 'harmon'
        assert case.dynamic_case_properties() == {'winner': 'Harmon'}
        assert case.indices[0].identifier == 'parent'
        assert case.indices[0].referenced_id == parent_case.case_id
        assert case.indices[0].referenced_type == 'player'
        assert case.indices[0].relationship == 'child'
        assert case.indices[0].referenced_case.case_id == parent_case.case_id

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
        assert set(res.keys()) == set(['case', 'form_id'])

        case = CommCareCase.objects.get_case(res['case']['case_id'], self.domain)
        assert case.indices[0].referenced_id == parent_case.case_id

    def test_set_parent_by_bad_external_id(self):
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
        assert res['error'] == "Could not find a case with external_id 'MISSING'"

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
        assert res['error'] == "Property relationship is required when creating or updating case indices"

    def test_delete_index(self):
        # aka remove child case
        parent_case = self._make_case()
        child_case = self._make_case(parent_id=parent_case.case_id)
        assert [c.case_id for c in parent_case.get_subcases()] == [child_case.case_id]

        res = self._update_case(child_case.case_id, {
            'indices': {
                'parent': {
                    'case_id': '',
                    'case_type': 'player',
                    'relationship': 'child',
                },
            },
        })
        assert res.status_code == 200

        parent_case = CommCareCase.objects.get_case(parent_case.case_id, self.domain)
        assert parent_case.get_subcases() == []

        child_case = CommCareCase.objects.get_case(child_case.case_id, self.domain)
        assert child_case.get_index('parent').referenced_id == ''

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
        assert set(res.keys()) == set(['cases', 'form_id'])

        updated_case = CommCareCase.objects.get_case(existing_case.case_id, self.domain)
        assert updated_case.name == 'Beth Harmon'

        new_case = CommCareCase.objects.get_case_by_external_id(self.domain, 'jolene')
        assert new_case.name == 'Jolene'

    def test_bulk_without_create_flag(self):
        res = self._bulk_update_cases([{
            # valid except it needs 'create' specified
            'case_type': 'player',
            'case_name': 'Jolene',
            'owner_id': 'methuen_home',
        }])
        assert res.status_code == 400
        assert "A 'create' flag is required for each update." in res.json()['error']

    def test_attempt_create_with_case_id(self):
        res = self._bulk_update_cases([{
            'create': True,
            'case_type': 'player',
            'case_name': 'Jolene',
            'owner_id': 'methuen_home',
            'case_id': 'somethingmalicious',
        }])
        assert res.status_code == 400
        assert "You cannot specify case_id when creating a new case" in res.json()['error']

    def test_bulk_update_too_big(self):
        res = self._bulk_update_cases([
            {'create': True, 'case_name': f'case {i}', 'case_type': 'player'}
            for i in range(103)
        ])
        assert res.status_code == 400
        assert res.json() == {'error': "You cannot submit more than 100 updates in a single request"}

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
        assert res.json()['error'] == "No case found with ID 'notarealcaseid'"
        assert CommCareCase.objects.get_case_ids_in_domain(self.domain) == []

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
        assert res.status_code == 200
        parent = CommCareCase.objects.get_case_by_external_id(self.domain, 'beth')
        child = CommCareCase.objects.get_case_by_external_id(self.domain, 'harmon-luchenko')
        assert parent.case_id == child.get_index('parent').referenced_id

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
        assert res.status_code == 400
        assert res.json()['error'] == "Could not find a case with temporary_id 'MISSING'"

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
        assert res.status_code == 200
        parent = CommCareCase.objects.get_case_by_external_id(self.domain, 'beth')
        child = CommCareCase.objects.get_case_by_external_id(self.domain, 'harmon-luchenko')
        assert parent.case_id == child.get_index('parent').referenced_id

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
        assert res.status_code == 200
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        assert case.dynamic_case_properties().get('champion') == 'true'

    def test_update_by_external_id_doesnt_exist(self):
        res = self.client.put(
            reverse('case_api', args=(self.domain,)),
            {
                'external_id': 'notarealcaseid',
                'properties': {'champion': 'true'},
            },
            content_type="application/json;charset=utf-8",
        )
        assert res.status_code == 400
        assert res.json()['error'] == "Could not find a case with external_id 'notarealcaseid'"

    def test_update_by_external_id_with_bad_create(self):
        case = self._make_case()
        res = self.client.put(
            reverse('case_api', args=(self.domain,)),
            {
                'external_id': case.external_id,
                'properties': {'champion': 'true'},
                'create': True,  # Only valid in bulk operations
            },
            content_type="application/json;charset=utf-8",
        )
        assert res.status_code == 400
        assert res.json()['error'] == "'create' is not a valid field."

    def test_single_update_with_list(self):
        case = self._make_case()
        res = self.client.put(
            reverse('case_api_detail_ext', args=(self.domain, case.external_id)),
            [{'properties': {'champion': 'true'}}],
            content_type="application/json;charset=utf-8",
        )
        assert res.status_code == 400
        assert res.json()['error'] == 'Payload must be a single JSON object'

    def test_bulk_update_by_external_id(self):
        case = self._make_case()
        res = self._bulk_update_cases([{
            'create': False,
            'external_id': case.external_id,
            'owner_id': 'us_chess_federation',
        }])
        assert res.status_code == 200
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        assert case.owner_id == 'us_chess_federation'

    def test_bulk_update_external_id_doesnt_exist(self):
        res = self._bulk_update_cases([{
            'create': False,
            'external_id': 'notarealcaseid',
            'owner_id': 'us_chess_federation',
        }])
        assert res.status_code == 400
        assert res.json()['error'] == "Could not find a case with external_id 'notarealcaseid'"

    def test_non_json_data(self):
        res = self._create_case("this isn't json")
        assert res.status_code == 400
        assert res.json() == {'error': "Payload must be valid JSON"}

    def test_missing_required_field(self):
        res = self._create_case({
            # case_name is not provided!
            'case_type': 'player',
            'owner_id': 'methuen_home',
            'properties': {'dob': '1948-11-02'},
        })
        assert res.status_code == 400
        assert res.json() == {'error': "Property case_name is required."}

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
        assert res.status_code == 400
        assert res.json() == {
            'error': "Error with case property 'age'. Values must be strings, received '72'"
        }

    def test_non_xml_properties(self):
        res = self._create_case({
            'case_type': 'player',
            'case_name': 'Elizabeth Harmon',
            'owner_id': 'methuen_home',
            'properties': {'not good': 'tsk tsk'},
        })
        assert res.status_code == 400
        msg = "Error with case property 'not good'. Case property names must be valid XML identifiers."
        assert res.json()['error'] == msg

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
        assert res.status_code == 400
        msg = ("Error with index 'Robert'); DROP TABLE students;--'. "
               "Index names must be valid XML identifiers.")
        assert res.json()['error'] == msg

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
        assert res.status_code == 400
        assert "InvalidCaseIndex" in res.json()['error']
        form = XFormInstance.objects.get_form(res.json()['form_id'])
        assert form.is_error

    def test_unset_external_id(self):
        case = self._make_case()
        assert case.external_id == '1'

        res = self._update_case(case.case_id, {
            'external_id': '',
        })
        assert res.status_code == 200
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        assert case.external_id == ''

    def test_omitting_external_id_doesnt_clear_it(self):
        case = self._make_case()
        assert case.external_id == '1'

        res = self._update_case(case.case_id, {
            'properties': {'champion': 'true'},
        })
        assert res.status_code == 200
        case = CommCareCase.objects.get_case(case.case_id, self.domain)
        assert case.external_id == '1'

    def test_urls_without_trailing_slash(self):
        case_id = self._make_case().case_id
        urls = [
            (self.client.post, reverse('case_api', args=(self.domain,)).rstrip("/")),
            (self.client.put, reverse('case_api_detail', args=(self.domain, case_id)).rstrip("/")),
            (self.client.post, reverse('case_api_v0.6', args=(self.domain,)).rstrip("/")),
            (self.client.put, reverse('case_api_v0.6_detail', args=(self.domain, case_id)).rstrip("/")),
        ]
        for request_fn, url in urls:
            res = request_fn(
                url,
                {'body': 'bad case update format'},
                content_type="application/json;charset=utf-8",
                HTTP_USER_AGENT="user agent string",
            )
            # These requests should return a 400 because of the bad body, not a 301 redirect
            assert res.status_code == 400

    def test_case_name_twice(self):
        case = self._make_case()
        res = self._update_case(case.case_id, {
            'case_name': 'Beth Harmon',
            'owner_id': 'us_chess_federation',
            'properties': {
                'rank': '2100',
                'case_name': 'Beth Harmon',  # ERROR
                'champion': 'true',
            },
        })
        assert res.status_code == 400
        msg = "Error with case property 'case_name'. This must be specified at the top level."
        assert res.json()['error'] == msg

    @patch("corehq.apps.hqcase.views.handle_case_update")
    def test_post_without_external_id_calls_with_is_creation_true(self, mock_handle_update):
        mock_handle_update.return_value = self._get_update_return()

        with patch(
            "corehq.apps.hqcase.views.serialize_case",
            return_value={"case_id": "new-case"},
        ):
            response = self.client.post(
                reverse("case_api", args=(self.domain,)),
                json.dumps(
                    {
                        "case_type": "patient",
                        "case_name": "Jane Doe",
                    }
                ),
                content_type="application/json",
                HTTP_USER_AGENT="test-agent",
            )

        assert response.status_code == 200
        mock_handle_update.assert_called_once()
        call_kwargs = mock_handle_update.call_args[1]
        assert call_kwargs["is_creation"]

    @patch("corehq.apps.hqcase.views.handle_case_update")
    def test_put_with_case_id_calls_with_is_creation_false(self, mock_handle_update):
        mock_handle_update.return_value = self._get_update_return()

        with patch(
            "corehq.apps.hqcase.views.serialize_case",
            return_value={"case_id": "case-123"},
        ):
            response = self.client.put(
                f"/a/{self.domain}/api/case/v2/case-123/",
                json.dumps(
                    {
                        "case_name": "Updated Name",
                        "external_id": "ext-456",
                    }
                ),
                content_type="application/json",
                HTTP_USER_AGENT="test-agent",
            )

        assert response.status_code == 200
        mock_handle_update.assert_called_once()
        call_kwargs = mock_handle_update.call_args[1]
        assert not call_kwargs["is_creation"]

    @staticmethod
    def _get_update_return():
        """Helper method to create mock return value for handle_case_update"""
        mock_xform = MagicMock(spec=XFormInstance)
        mock_xform.form_id = "test-form-id"
        mock_case = MagicMock(spec=CommCareCase)
        return mock_xform, mock_case

    def test_upsert_by_external_id_is_idempotent(self):
        """
        Test that sending the same PUT request twice to the external_id
        endpoint is idempotent.

        The first request should create a case, and the second should update it,
        not create a duplicate.
        """
        external_id = 'idempotency-test-123'
        payload = {
            'case_type': 'player',
            'case_name': 'Magnus Carlsen',
            'owner_id': 'world_chess',
            'properties': {
                'rank': '2800',
                'country': 'Norway',
            },
        }

        # First request - should create the case
        res1 = self.client.put(
            reverse('case_api_detail_ext', args=(self.domain, external_id)),
            payload,
            content_type="application/json;charset=utf-8",
            HTTP_USER_AGENT="user agent string",
        )
        assert res1.status_code == 200
        case_id_1 = res1.json()['case']['case_id']

        # Second request - should update the same case, not create a duplicate
        res2 = self.client.put(
            reverse('case_api_detail_ext', args=(self.domain, external_id)),
            payload,
            content_type="application/json;charset=utf-8",
            HTTP_USER_AGENT="user agent string",
        )
        assert res2.status_code == 200
        case_id_2 = res2.json()['case']['case_id']

        # Verify idempotency - both requests should reference the same case
        assert case_id_1 == case_id_2, (
            "Expected the same case to be updated, not a duplicate created"
        )

        # Verify only one case exists with this external_id
        cases = CommCareCase.objects.get_case_ids_in_domain(self.domain)
        assert len(cases) == 1, f"Expected 1 case, found {len(cases)}"

        # Verify the case has the correct properties
        case = CommCareCase.objects.get_case(case_id_1, self.domain)
        assert case.external_id == external_id
        assert case.name == 'Magnus Carlsen'
        assert case.type == 'player'
        assert case.owner_id == 'world_chess'
        assert case.dynamic_case_properties() == {
            'rank': '2800',
            'country': 'Norway',
        }
