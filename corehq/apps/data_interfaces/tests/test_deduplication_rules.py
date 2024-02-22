import json
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase

from corehq.apps.users.models import FakeUser
from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.views import (
    DeduplicationRuleCreateView,
    DeduplicationRuleEditView,
    HttpResponseRedirect,
)
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.tests.utils import es_test


@es_test(requires=[case_adapter], setup_class=True)
class DeduplicationRuleCreateViewTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain-create'
        cls.user = FakeUser(username='test-user')

    @patch('corehq.apps.data_interfaces.views.messages')
    @patch('corehq.apps.data_interfaces.views.reverse', Mock(return_value='url'))
    def test_newly_created_rule_is_inactive(self, *args):
        view = DeduplicationRuleCreateView()
        view.args = []
        view.kwargs = {}

        request = self._create_request(params={
            'properties_to_update': json.dumps({}),
            'case_properties': json.dumps({}),
            'name': 'test_name',
            'case_type': 'test_type',
            'match_type': 'ttype',
            'case-filter-property_match_definitions': json.dumps([]),
            'case-filter-location_filter_definition': json.dumps([]),
        })

        view.post(request)
        self.assertEqual(1, len(AutomaticUpdateRule.objects.all()))
        self.assertEqual(False, AutomaticUpdateRule.objects.all()[0].active)

    @patch('corehq.apps.data_interfaces.views.messages')
    @patch('corehq.apps.data_interfaces.views.DataInterfaceSection.get')
    def test_creating_rule_with_existing_name_fails(self, *args):
        rule_name = 'test_name'
        case_type = 'test_type'
        self._save_dummy_rule(rule_name, case_type)
        # Existing rules count
        existing_rules = AutomaticUpdateRule.objects.all()
        self.assertEqual(1, len(existing_rules))
        view = DeduplicationRuleCreateView()
        view.args = []
        view.kwargs = {}
        request = self._create_request(params={
            'properties_to_update': json.dumps({}),
            'case_properties': json.dumps({}),
            'name': rule_name,
            'case_type': case_type,
            'match_type': 'ttype',
            'case-filter-property_match_definitions': json.dumps([]),
            'case-filter-location_filter_definition': json.dumps([]),
        })
        view.post(request)
        # Rules count after making call
        latest_rules = AutomaticUpdateRule.objects.all()
        self.assertEqual(1, len(latest_rules))
        self.assertEqual(existing_rules[0], latest_rules[0])

    def _create_request(self, params=None, method='post'):
        url = 'dummy_url'
        if method == 'get':
            request = RequestFactory().get(url, params)
        else:
            request = RequestFactory().post(url, params)
        request.domain = self.domain
        request.couch_user = self.user
        return request

    def _save_dummy_rule(self, rule_name, case_type):
        res = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name=rule_name,
            case_type=case_type,
            active=False,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )
        return res.id


@es_test(requires=[case_adapter], setup_class=True)
class DeduplicationRuleEditViewTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'test-domain-edit'

    @patch('corehq.apps.data_interfaces.views.messages')
    @patch('corehq.apps.data_interfaces.views.DeduplicationRuleEditView.dedupe_action')
    @patch('corehq.apps.data_interfaces.views.reverse', Mock(return_value='url'))
    def test_when_rule_edited_doesnt_throw_error(self, *args):
        rule_name = 'test_rule'
        case_type = 'test_type'
        rule_id = self._save_dummy_rule(rule_name, case_type)

        view = DeduplicationRuleEditView()
        view.args = []
        view.kwargs = {"rule_id": rule_id, "domain": self.domain}
        request = self._create_request(params={
            'properties_to_update': json.dumps({}),
            'case_properties': json.dumps({}),
            'name': rule_name,
            'case_type': case_type,
            'match_type': 'ttype',
            'case-filter-property_match_definitions': json.dumps([]),
            'case-filter-location_filter_definition': json.dumps([]),
        })
        resp = view.post(request)
        self.assertEqual(HttpResponseRedirect, type(resp))

    def _save_dummy_rule(self, rule_name, case_type):
        res = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name=rule_name,
            case_type=case_type,
            active=False,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
        )
        return res.id

    def _create_request(self, params=None, method='post'):
        url = 'dummy_url'
        if method == 'get':
            request = RequestFactory().get(url, params)
        else:
            request = RequestFactory().post(url, params)
        request.domain = self.domain
        return request
