import uuid
from unittest import skip

from django.test import TestCase
from django.urls import reverse

from casexml.apps.case.mock import CaseBlock
from couchforms.models import XFormError

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import WebUser
from corehq.form_processor.interfaces.dbaccessors import (
    CaseAccessors,
    FormAccessors,
)
from corehq.form_processor.tests.utils import FormProcessorTestUtils


class TestCaseAPI(TestCase):
    domain = 'test-update-cases'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(cls.domain)
        cls.web_user = WebUser.create(cls.domain, 'netflix', 'password', None, None)
        cls.web_user.is_superuser = True  # in pre-release, this is superuser-only
        cls.web_user.save()
        cls.case_accessor = CaseAccessors(cls.domain)
        cls.form_accessor = FormAccessors(cls.domain)

    def setUp(self):
        self.client.login(username='netflix', password='password')

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases(self.domain)

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super().tearDownClass()

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

    def test_create_case(self):
        res = self._create_case({
            # notable exclusions: case_id, date_opened, date_modified
            '@case_type': 'player',
            '@case_name': 'Elizabeth Harmon',
            '@owner_id': 'methuen_home',
            'properties': {
                'external_id': '1',
                'sport': 'chess',
                'dob': '1948-11-02',
            },
        }).json()
        self.assertItemsEqual(res.keys(), ['@case_id', '@form_id'])
        case = self.case_accessor.get_case(res['@case_id'])
        self.assertEqual(case.domain, self.domain)
        self.assertEqual(case.type, 'player')
        self.assertEqual(case.name, 'Elizabeth Harmon')
        self.assertEqual(case.owner_id, 'methuen_home')
        self.assertEqual(case.opened_by, self.web_user.user_id)
        self.assertEqual(case.external_id, '1')
        self.assertEqual(case.dynamic_case_properties(), {
            'dob': '1948-11-02',
            'sport': 'chess',
        })

        xform = self.form_accessor.get_form(res['@form_id'])
        self.assertEqual(xform.xmlns, 'http://commcarehq.org/case_api')
        self.assertEqual(xform.metadata.userID, self.web_user.user_id)
        self.assertEqual(xform.metadata.deviceID, 'user agent string')

    def _make_case(self):
        xform, cases = submit_case_blocks([CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='player',
            case_name='Elizabeth Harmon',
            owner_id='methuen_home',
            create=True,
            update={
                'external_id': '1',
                'sport': 'chess',
                'rank': '1600',
                'dob': '1948-11-02',
            }
        ).as_text()], domain=self.domain)
        return cases[0]

    def test_update_case(self):
        case = self._make_case()

        res = self._update_case(case.case_id, {
            # notable exclusions: case_id, date_opened, date_modified, case_type
            '@case_name': 'Beth Harmon',
            '@owner_id': 'us_chess_federation',
            'properties': {
                'rank': '2100',
                'champion': 'true',
            },
        }).json()
        self.assertItemsEqual(res.keys(), ['@case_id', '@form_id'])

        case = self.case_accessor.get_case(case.case_id)
        self.assertEqual(case.name, 'Beth Harmon')
        self.assertEqual(case.owner_id, 'us_chess_federation')
        self.assertEqual(case.dynamic_case_properties(), {
            'champion': 'true',
            'dob': '1948-11-02',
            'rank': '2100',
            'sport': 'chess',
        })

    def test_create_child_case(self):
        parent_case = self._make_case()
        res = self._create_case({
            '@case_type': 'match',
            '@case_name': 'Harmon/Luchenko',
            '@owner_id': 'harmon',
            'properties': {
                'external_id': '23',
                'winner': 'Harmon',
            },
            'indices': {
                'parent': {
                    'case_id': parent_case.case_id,
                    '@case_type': 'player',
                    '@relationship': 'child',
                },
            },
        }).json()
        self.assertItemsEqual(res.keys(), ['@case_id', '@form_id'])

        case = self.case_accessor.get_case(res['@case_id'])
        self.assertEqual(case.name, 'Harmon/Luchenko')
        self.assertEqual(case.owner_id, 'harmon')
        self.assertEqual(case.external_id, '23')
        self.assertEqual(case.dynamic_case_properties(), {'winner': 'Harmon'})
        self.assertEqual(case.indices[0].identifier, 'parent')
        self.assertEqual(case.indices[0].referenced_id, parent_case.case_id)
        self.assertEqual(case.indices[0].referenced_type, 'player')
        self.assertEqual(case.indices[0].relationship, 'child')
        self.assertEqual(case.indices[0].referenced_case.case_id, parent_case.case_id)

    @skip("not yet implemented")
    def test_bulk_action(self):
        existing_case = self._make_case()
        res = self._bulk_update_cases([
            {
                # update existing case
                '@case_id': existing_case.case_id,
                '@case_name': 'Beth Harmon',
                '@owner_id': 'us_chess_federation',
                'properties': {
                    'rank': '2100',
                    'champion': 'true',
                },
            },
            {
                # No case_id means this is a new case
                '@case_type': 'player',
                '@case_name': 'Jolene',
                '@owner_id': 'methuen_home',
                'properties': {
                    'external_id': '2',
                    'sport': 'squash',
                    'dob': '1947-03-09',
                },
            },
        ]).json()
        #  only returns a single form ID - chunking should happen in the client
        self.assertItemsEqual(res.keys(), ['@case_ids', '@form_id'])

        updated_case = self.case_accessor.get_case(existing_case.case_id)
        self.assertEqual(updated_case.name, 'Beth Harmon')

        new_case = self.case_accessor.get_case(res['@case_ids'][1])
        self.assertEqual(new_case.name, 'Jolene')

    @skip("not yet implemented")
    def test_create_parent_and_child_together(self):
        # TODO? Since this API doesn't let you provide your own case IDs, you
        # can't reference uncreated cases in indices unless we invent some
        # syntax specifically for that. Thinking about leaving out of scope for
        # v1, at least (it wouldn't be a breaking change to add in later).
        pass

    def test_non_json_data(self):
        res = self._create_case("this isn't json")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {'error': "Payload must be valid JSON"})

    def test_missing_required_field(self):
        res = self._create_case({
            # @case_name is not provided!
            '@case_type': 'player',
            '@owner_id': 'methuen_home',
            'properties': {'dob': '1948-11-02'},
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {'error': "Property @case_name is required."})

    def test_invalid_properties(self):
        res = self._create_case({
            '@case_name': 'Beth Harmon',
            '@case_type': 'player',
            '@owner_id': 'methuen_home',
            'properties': {
                'dob': '1948-11-02',
                'age': 72,  # Can't pass integers
            },
        })
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.json(), {'error': "Case properties must be strings"})

    def test_bad_index_reference(self):
        res = self._create_case({
            '@case_type': 'match',
            '@case_name': 'Harmon/Luchenko',
            '@owner_id': 'harmon',
            'properties': {
                'external_id': '23',
            },
            'indices': {
                'parent': {
                    'case_id': 'bad404bad',  # This doesn't exist
                    '@case_type': 'player',
                    '@relationship': 'child',
                },
            },
        })
        self.assertEqual(res.status_code, 400)
        self.assertIn("InvalidCaseIndex", res.json()['error'])
        form = self.form_accessor.get_form(res.json()['@form_id'])
        self.assertIsInstance(form, XFormError)
