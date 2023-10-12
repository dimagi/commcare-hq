import json
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase

from corehq.apps.data_interfaces.models import AutomaticUpdateRule
from corehq.apps.data_interfaces.views import (
    DeduplicationRuleCreateView,
    DeduplicationRuleEditView,
    HttpResponseRedirect,
)
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.tests.utils import es_test
from django.contrib.messages.storage import default_storage


@es_test(requires=[case_adapter], setup_class=True)
@patch('corehq.apps.data_interfaces.views.reverse', Mock(return_value='url'))
class DeduplicationRuleCreateViewTest(TestCase):

    def setUp(self):
        super().setUp()
        self.domain = 'test-domain-create'
        self.view = self._create_view()

    def test_newly_created_rule_is_inactive(self, *args):
        request = self._create_creation_request()

        self.view.post(request)

        rule = AutomaticUpdateRule.objects.get(domain=self.domain,
                                               workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertFalse(rule.active)

    @patch('corehq.apps.data_interfaces.views.DataInterfaceSection.get')
    def test_creating_rule_with_existing_name_fails(self, *args):
        self._save_dedupe_rule('existing_name', 'test_type')
        existing_rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        request = self._create_creation_request(name='existing_name')

        self.view.post(request)

        latest_rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(existing_rule, latest_rule)
        # Hacky -- there are cleaner ways to look at messages, but that would
        # require a valid response object, and we don't have that when mocking out 'GET'
        self.assertEqual(request._messages._queued_messages[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>A rule with name existing_name already exists</li></ul>')

    def test_create_minimal_rule(self):
        request = self._create_creation_request(
            name='TestRule', case_type='case', case_properties=['email'], match_type='ALL'
        )

        self.view.post(request)

        rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        criteria = rule.caserulecriteria_set.all()
        action = rule.caseruleaction_set.get().case_deduplication_action_definition
        self.assertEqual(rule.name, 'TestRule')
        self.assertEqual(rule.case_type, 'case')
        self.assertEqual(len(criteria), 0)
        self.assertEqual(action.match_type, 'ALL')
        self.assertEqual(action.case_properties, ['email'])
        self.assertEqual(action.properties_to_update, [])

    def test_create_rule_with_actions(self):
        request = self._create_creation_request(
            properties_to_update=[{'name': 'level', 'valueType': 'EXACT', 'value': 'test'}]
        )

        self.view.post(request)
        rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        action = rule.caseruleaction_set.get().case_deduplication_action_definition
        self.assertEqual(action.properties_to_update, [{'name': 'level', 'value_type': 'EXACT', 'value': 'test'}])

    def test_create_rule_with_filters(self):
        request = self._create_creation_request(
            match_filter=[{'property_name': 'name', 'property_value': 'someName', 'match_type': 'EQUAL'}])

        self.view.post(request)

        rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        criteria = rule.caserulecriteria_set.get().match_property_definition
        self.assertEqual(criteria.match_type, 'EQUAL')
        self.assertEqual(criteria.property_name, 'name')
        self.assertEqual(criteria.property_value, 'someName')

    @patch('corehq.apps.data_interfaces.views.DataInterfaceSection.get')
    def test_duplicate_matching_parameters_fails(self, *args):
        request = self._create_creation_request(case_properties=['email', 'email'])

        self.view.post(request)

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(0, rules.count())
        self.assertEqual(request._messages._queued_messages[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>Matching case properties must be unique</li></ul>')

    @patch('corehq.apps.data_interfaces.views.DataInterfaceSection.get')
    def test_duplicate_updating_properties_fails(self, *args):
        request = self._create_creation_request(
            properties_to_update=[
                {'name': 'prop1', 'valueType': 'EXACT', 'value': 'test'},
                {'name': 'prop1', 'valueType': 'EXACT', 'value': 'test2'},
            ]
        )

        self.view.post(request)

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(0, rules.count())
        self.assertEqual(request._messages._queued_messages[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>Action case properties must be unique</li></ul>')

    @patch('corehq.apps.data_interfaces.views.DataInterfaceSection.get')
    def test_updating_reserved_property_fails(self, *args):
        request = self._create_creation_request(
            properties_to_update=[{'name': 'name', 'valueType': 'EXACT', 'value': 'test'}]
        )

        self.view.post(request)

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(0, rules.count())
        self.assertEqual(request._messages._queued_messages[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>You cannot update reserved property: name</li></ul>')

    @patch('corehq.apps.data_interfaces.views.DataInterfaceSection.get')
    def test_updating_match_property_fails(self, *args):
        request = self._create_creation_request(
            case_properties=['email'],
            properties_to_update=[{'name': 'email', 'valueType': 'EXACT', 'value': 'test'}]
        )

        self.view.post(request)

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(0, rules.count())
        self.assertEqual(request._messages._queued_messages[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>You cannot update properties that are used to match a duplicate.</li></ul>')

    def _create_creation_request(self,
        name='TestRule',
        case_type='case',
        case_properties=["email"],
        match_type='ALL',
        properties_to_update=None,
        match_filter=None,
    ):
        params = {
            'name': name,
            'case_type': case_type,
            'case_properties': json.dumps([{"name": prop} for prop in case_properties]),
            'match_type': match_type,
            'case-filter-property_match_definitions': json.dumps(match_filter or []),
            'case-filter-location_filter_definition': json.dumps([])
        }

        params['properties_to_update'] = json.dumps(properties_to_update or [])

        request = RequestFactory().post('dummy_url', params)
        request.domain = self.domain
        request._messages = default_storage(request)
        return request

    def _create_view(self):
        view = DeduplicationRuleCreateView()
        view.args = []
        view.kwargs = {}
        return view

    def _save_dedupe_rule(self, rule_name, case_type):
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
