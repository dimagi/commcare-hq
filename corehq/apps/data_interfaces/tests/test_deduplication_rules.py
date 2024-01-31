import json
from unittest.mock import Mock, patch

from django.test import RequestFactory, TestCase

from corehq.apps.data_interfaces import views as dedupe_views
from corehq.apps.data_interfaces.models import AutomaticUpdateRule, CaseDeduplicationActionDefinition
from corehq.apps.data_interfaces.views import (
    DeduplicationRuleCreateView,
    DeduplicationRuleEditView,
    HttpResponseRedirect,
)
from corehq.apps.es.cases import case_adapter
from corehq.apps.es.tests.utils import es_test
from django.contrib.messages import get_messages
from django.contrib.messages.storage import default_storage
from corehq.util.test_utils import flag_enabled, flag_disabled


@es_test(requires=[case_adapter], setup_class=True)
@patch.object(dedupe_views, 'reverse', Mock(return_value='url'))
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

    @patch.object(dedupe_views.DataInterfaceSection, 'get')
    def test_creating_rule_with_existing_name_fails(self, *args):
        self._save_dedupe_rule('existing_name', 'test_type')
        existing_rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        request = self._create_creation_request(name='existing_name')

        self.view.post(request)

        latest_rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(existing_rule, latest_rule)
        self.assertEqual(list(get_messages(request))[0].message,
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

    @flag_enabled('CASE_DEDUPE')
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

    @patch.object(dedupe_views.DataInterfaceSection, 'get')
    def test_duplicate_matching_parameters_fails(self, *args):
        request = self._create_creation_request(case_properties=['email', 'email'])

        self.view.post(request)

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(0, rules.count())
        self.assertEqual(list(get_messages(request))[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>Matching case properties must be unique</li></ul>')

    @flag_enabled('CASE_DEDUPE')
    @patch.object(dedupe_views.DataInterfaceSection, 'get')
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
        self.assertEqual(list(get_messages(request))[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>Action case properties must be unique</li></ul>')

    @flag_enabled('CASE_DEDUPE')
    @patch.object(dedupe_views.DataInterfaceSection, 'get')
    def test_updating_reserved_property_fails(self, *args):
        request = self._create_creation_request(
            properties_to_update=[{'name': 'name', 'valueType': 'EXACT', 'value': 'test'}]
        )

        self.view.post(request)

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(0, rules.count())
        self.assertEqual(list(get_messages(request))[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>You cannot update reserved property: name</li></ul>')

    @flag_enabled('CASE_DEDUPE')
    @patch.object(dedupe_views.DataInterfaceSection, 'get')
    def test_updating_match_property_fails(self, *args):
        request = self._create_creation_request(
            case_properties=['email'],
            properties_to_update=[{'name': 'email', 'valueType': 'EXACT', 'value': 'test'}]
        )

        self.view.post(request)

        rules = AutomaticUpdateRule.objects.filter(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        self.assertEqual(0, rules.count())
        self.assertEqual(list(get_messages(request))[0].message,
            'Deduplication rule not saved due to the following issues: '
            '<ul><li>You cannot update properties that are used to match a duplicate.</li></ul>')

    @flag_disabled('CASE_DEDUPE')
    def test_creating_rule_with_actions_but_no_toggle_ignores_actions(self, *args):
        request = self._create_creation_request(
            properties_to_update=[{"name": "level", "valueType": "EXACT", "value": "test"}]
        )

        self.view.post(request)

        rule = AutomaticUpdateRule.objects.get(
            domain=self.domain, workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE)
        action = rule.caseruleaction_set.get().case_deduplication_action_definition
        self.assertEqual(action.properties_to_update, [])

    def _create_creation_request(self,
        name='TestRule',
        case_type='case',
        case_properties=['email'],
        match_type='ALL',
        properties_to_update=None,
        match_filter=None,
    ):
        params = {
            'name': name,
            'case_type': case_type,
            'case_properties': json.dumps([{'name': prop} for prop in case_properties]),
            'match_type': match_type,
            'case-filter-property_match_definitions': json.dumps(match_filter or []),
            'case-filter-location_filter_definition': json.dumps([])
        }

        if properties_to_update:
            params['properties_to_update'] = json.dumps(properties_to_update)

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
@patch.object(dedupe_views, 'reverse', Mock(return_value='url'))
class DeduplicationRuleEditViewTest(TestCase):
    def setUp(self):
        self.domain = 'test-domain-edit'

    def test_when_rule_edited_doesnt_throw_error(self):
        rule = self._create_rule()
        view = self._create_view(rule)
        request = self._create_update_request(rule, name='UpdatedName')

        resp = view.post(request)

        self.assertEqual(HttpResponseRedirect, type(resp))

    def test_rule_can_update_properties(self):
        rule = self._create_rule(name='TestRule1')
        view = self._create_view(rule)
        request = self._create_update_request(rule, name='TestRule2')

        view.post(request)

        updatedRule = AutomaticUpdateRule.objects.get(id=rule.id)
        self.assertEqual(updatedRule.name, 'TestRule2')

    def test_cannot_edit_backfilling_rule(self):
        rule = self._create_rule(name='TestRule1', is_backfilling=True)
        view = self._create_view(rule)
        request = self._create_update_request(rule, name='TestRule2')

        view.post(request)

        updatedRule = AutomaticUpdateRule.objects.get(id=rule.id)
        self.assertEqual(updatedRule.name, 'TestRule1')
        self.assertEqual(list(get_messages(request))[0].message,
            'Rule TestRule1 is currently backfilling and cannot be edited')

    @patch.object(dedupe_views, 'reset_and_backfill_deduplicate_rule')
    def test_updated_rule_starts_backfilling(self, mock_backfill):
        rule = self._create_rule(name='TestRule1')
        view = self._create_view(rule)
        request = self._create_update_request(rule, name='TestRule2')

        view.post(request)

        mock_backfill.assert_called()
        self.assertEqual(list(get_messages(request))[0].message,
            'Rule TestRule2 was updated, and has been queued for backfilling')

    @flag_disabled('CASE_DEDUPE')
    def test_rule_with_actions_loses_actions_when_updated_with_the_toggle_disabled(self):
        rule = self._create_rule(
            name='TestRule1',
            properties_to_update=[{"name": "level", "value_type": "EXACT", "value": "test"}]
        )
        view = self._create_view(rule)
        request = self._create_update_request(rule, name='TestRule2', actions_enabled=False)

        view.post(request)
        updatedRule = AutomaticUpdateRule.objects.get(id=rule.id)
        action = updatedRule.caseruleaction_set.get().case_deduplication_action_definition
        self.assertEqual(action.properties_to_update, [])

    def _create_view(self, rule):
        view = DeduplicationRuleEditView()
        view.args = []
        view.kwargs = {'rule_id': rule.id, 'domain': self.domain}
        return view

    def _create_rule(
        self,
        name='TestRule',
        case_type='case',
        case_properties=['email'],
        match_type='ALL',
        properties_to_update=[],
        is_backfilling=False,
    ):
        rule = AutomaticUpdateRule.objects.create(
            name=name,
            domain=self.domain,
            case_type=case_type,
            workflow=AutomaticUpdateRule.WORKFLOW_DEDUPLICATE,
            locked_for_editing=is_backfilling,
        )
        rule.add_action(CaseDeduplicationActionDefinition,
                        case_properties=case_properties,
                        match_type=match_type,
                        properties_to_update=properties_to_update)

        return rule

    def _create_update_request(
        self,
        rule,
        name=None,
        case_type=None,
        case_properties=None,
        match_type=None,
        properties_to_update=None,
        actions_enabled=True
    ):
        action = CaseDeduplicationActionDefinition.from_rule(rule)
        params = {
            'name': name or rule.name,
            'case_type': case_type or rule.case_type,
            'match_type': match_type or action.match_type,
            'case_properties': json.dumps(
                self._transform_case_properties(case_properties or action.case_properties)),
            'case-filter-property_match_definitions': json.dumps([]),
            'case-filter-location_filter_definition': json.dumps([])
        }

        if actions_enabled:
            params['properties_to_update'] = json.dumps(
                self._transform_update_properties(properties_to_update or action.properties_to_update))

        request = RequestFactory().post('dummy_url', params)
        request.domain = self.domain
        request._messages = default_storage(request)
        return request

    def _transform_case_properties(self, case_properties):
        return [{'name': prop} for prop in case_properties]

    def _transform_update_properties(self, properties_to_update):
        return [
            {'name': prop['name'], 'valueType': prop['value_type'], 'value': prop['value']}
            for prop in properties_to_update
        ]
