from unittest.mock import patch, MagicMock
from django.test import SimpleTestCase
from datetime import date
from corehq.apps.data_interfaces.models import (
    CaseDeduplicationActionDefinition,
    ClosedParentDefinition,
    CreateScheduleInstanceActionDefinition,
    MatchPropertyDefinition,
    CustomMatchDefinition,
    UpdateCaseDefinition,
    CustomActionDefinition,
    LocationFilterDefinition,
    UCRFilterDefinition,
    CaseRuleCriteria,
    CaseRuleAction,
    AutomaticUpdateRule,
)


class MatchPropertyDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = MatchPropertyDefinition(
            property_name='test_name',
            property_value='test_value',
            match_type='test_type',
        )

        self.assertEqual(definition.to_dict(), {
            'property_name': 'test_name',
            'property_value': 'test_value',
            'match_type': 'test_type',
        })


class CustomMatchDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = CustomMatchDefinition(name='test_name')

        self.assertEqual(definition.to_dict(), {
            'name': 'test_name',
        })


class UpdateCaseDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = UpdateCaseDefinition(
            properties_to_update=['one', 'two', 'three'],
            close_case=False
        )

        self.assertEqual(definition.to_dict(), {
            'properties_to_update': ['one', 'two', 'three'],
            'close_case': False,
        })


class CustomActionDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = CustomActionDefinition(name='test_name')

        self.assertEqual(definition.to_dict(), {
            'name': 'test_name'
        })


class LocationFilterDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = LocationFilterDefinition(location_id='test_id', include_child_locations=False)

        self.assertEqual(definition.to_dict(), {
            'location_id': 'test_id',
            'include_child_locations': False
        })


class UCRFilterDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = UCRFilterDefinition(configured_filter={'type': 'test_type'})

        self.assertEqual(definition.to_dict(), {
            'configured_filter': {'type': 'test_type'}
        })


class CreateScheduleInstanceActionDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = CreateScheduleInstanceActionDefinition(
            recipients=['one', 'two', 'three'],
            reset_case_property_name='test_case_name',
            start_date_case_property='test_start',
            specific_start_date=date(2020, 2, 20),
            scheduler_module_info={'data': 'test'}
        )

        self.assertEqual(definition.to_dict(), {
            'recipients': ['one', 'two', 'three'],
            'reset_case_property_name': 'test_case_name',
            'start_date_case_property': 'test_start',
            'specific_start_date': date(2020, 2, 20),
            'scheduler_module_info': {'data': 'test'}
        })


class CaseDeduplicationActionDefinitionTests(SimpleTestCase):
    def test_to_dict_includes_all_fields(self):
        definition = CaseDeduplicationActionDefinition(
            match_type='test_type',
            case_properties=['prop1', 'prop2'],
            include_closed=True
        )

        self.assertEqual(definition.to_dict(), {
            'match_type': 'test_type',
            'case_properties': ['prop1', 'prop2'],
            'include_closed': True,
        })


class CaseRuleCriteriaTests(SimpleTestCase):
    def test_to_dict_includes_all_referenced_models(self):
        criteria = CaseRuleCriteria(
            match_property_definition=create_dict_mock(MatchPropertyDefinition, 'match'),
            custom_match_definition=create_dict_mock(CustomMatchDefinition, 'custom_match'),
            location_filter_definition=create_dict_mock(LocationFilterDefinition, 'location'),
            ucr_filter_definition=create_dict_mock(UCRFilterDefinition, 'ucr')
        )

        self.assertEqual(criteria.to_dict(), {
            'match_property_definition': 'match',
            'custom_match_definition': 'custom_match',
            'location_filter_definition': 'location',
            'ucr_filter_definition': 'ucr',
            'closed_parent_definition': False,
        })

    def test_to_dict_fills_in_missing_fields(self):
        criteria = CaseRuleCriteria()

        self.assertEqual(criteria.to_dict(), {
            'match_property_definition': None,
            'custom_match_definition': None,
            'location_filter_definition': None,
            'ucr_filter_definition': None,
            'closed_parent_definition': False,
        })

    def test_to_dict_with_closed_parent_definition_returns_true(self):
        criteria = CaseRuleCriteria(closed_parent_definition=ClosedParentDefinition())
        self.assertTrue(criteria.to_dict()['closed_parent_definition'])


class CaseRuleActionTests(SimpleTestCase):
    def test_to_dict_includes_all_referenced_models(self):
        action = CaseRuleAction(
            update_case_definition=create_dict_mock(UpdateCaseDefinition, 'update_case'),
            custom_action_definition=create_dict_mock(CustomActionDefinition, 'custom_action'),
            create_schedule_instance_definition=create_dict_mock(
                CreateScheduleInstanceActionDefinition, 'schedule'),
            case_deduplication_action_definition=create_dict_mock(CaseDeduplicationActionDefinition, 'dedupe')
        )

        self.assertEqual(action.to_dict(), {
            'update_case_definition': 'update_case',
            'custom_action_definition': 'custom_action',
            'create_schedule_instance_definition': 'schedule',
            'case_deduplication_action_definition': 'dedupe',
        })

    def test_to_dict_fills_in_missing_fields(self):
        action = CaseRuleAction()

        self.assertEqual(action.to_dict(), {
            'update_case_definition': None,
            'custom_action_definition': None,
            'create_schedule_instance_definition': None,
            'case_deduplication_action_definition': None
        })


class AutomaticUpdateRuleTests(SimpleTestCase):
    def test_to_json_includes_all_fields(self):
        rule = AutomaticUpdateRule(
            domain='test-domain',
            name='test-name',
            case_type='test-case',
            active=True,
            deleted=False,
            last_run=date(2020, 2, 20),
            filter_on_server_modified=True,
            server_modified_boundary=5,
            workflow='test-workflow',
            locked_for_editing=False,
            upstream_id='upstream_id',
            id=15,
        )

        self.assertEqual(rule.to_json(), {
            'domain': 'test-domain',
            'name': 'test-name',
            'case_type': 'test-case',
            'active': True,
            'deleted': False,
            'last_run': date(2020, 2, 20),
            'filter_on_server_modified': True,
            'server_modified_boundary': 5,
            'workflow': 'test-workflow',
            'locked_for_editing': False,
            'upstream_id': 'upstream_id',
            'id': 15,
        })

    def test_to_dict_includes_criteria_and_actions(self):
        rule = AutomaticUpdateRule()
        patch.object(rule, 'to_json', lambda: 'rule_data').start()

        self.criteria.extend([
            create_dict_mock(CaseRuleCriteria, 'criteria1'),
            create_dict_mock(CaseRuleCriteria, 'criteria2'),
        ])

        self.actions.extend([
            create_dict_mock(CaseRuleAction, 'action1'),
            create_dict_mock(CaseRuleAction, 'action2'),
        ])

        self.assertEqual(rule.to_dict(), {
            'rule': 'rule_data',
            'criteria': ['criteria1', 'criteria2'],
            'actions': ['action1', 'action2'],
        })

    def setUp(self):
        self.actions = []
        self.criteria = []

        criteria_set_mock = MagicMock()
        criteria_set_mock.all = lambda: self.criteria
        criteria_patcher = patch.object(AutomaticUpdateRule, 'caserulecriteria_set', criteria_set_mock)
        criteria_patcher.start()
        self.addCleanup(criteria_patcher.stop)

        action_set_mock = MagicMock()
        action_set_mock.all = lambda: self.actions
        action_patcher = patch.object(AutomaticUpdateRule, 'caseruleaction_set', action_set_mock)
        action_patcher.start()
        self.addCleanup(action_patcher.stop)


def create_dict_mock(class_, data):
    '''Create an empty object of the given class whose `to_dict` method returns the specified data'''
    obj = class_()
    patch.object(obj, 'to_dict', lambda: data).start()
    return obj
