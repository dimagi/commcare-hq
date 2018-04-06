from __future__ import absolute_import
from __future__ import unicode_literals
import json
from datetime import datetime
from django.test import TestCase
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    AutomaticUpdateRuleCriteria,
    AutomaticUpdateAction,
    CaseRuleCriteria,
    MatchPropertyDefinition,
    CustomMatchDefinition,
    ClosedParentDefinition,
    CaseRuleAction,
    UpdateCaseDefinition,
    CustomActionDefinition,
)


class TestCaseRuleMigration(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestCaseRuleMigration, cls).setUpClass()
        cls.domain = 'case-rule-migration'

    def delete_old_criteria_and_actions(self):
        AutomaticUpdateRuleCriteria.objects.filter(rule__domain=self.domain).delete()
        AutomaticUpdateAction.objects.filter(rule__domain=self.domain).delete()

    def delete_new_criteria_and_actions(self):
        for rule in AutomaticUpdateRule.objects.filter(domain=self.domain):
            for criteria in rule.caserulecriteria_set.all():
                criteria.definition.delete()
            rule.caserulecriteria_set.all().delete()

            for action in rule.caseruleaction_set.all():
                action.definition.delete()
            rule.caseruleaction_set.all().delete()

    def tearDown(self):
        self.delete_old_criteria_and_actions()
        self.delete_new_criteria_and_actions()
        AutomaticUpdateRule.objects.filter(domain=self.domain).delete()

    def assertCriteriaMigratedCorrectly(self, old_rule, new_rule, criteria_count):
        self.assertEqual(old_rule.automaticupdaterulecriteria_set.all().count(), criteria_count)
        self.assertEqual(CaseRuleCriteria.objects.count(), criteria_count)
        self.assertEqual(MatchPropertyDefinition.objects.count(), criteria_count)
        self.assertEqual(CustomMatchDefinition.objects.count(), 0)
        self.assertEqual(ClosedParentDefinition.objects.count(), 0)

        expected_criteria = []
        for criteria in old_rule.automaticupdaterulecriteria_set.all():
            property_value = criteria.property_value
            if criteria.match_type == AutomaticUpdateRuleCriteria.MATCH_DAYS_BEFORE:
                property_value = int(property_value) * -1
                property_value = str(property_value)

            expected_criteria.append({
                'property_name': criteria.property_name,
                'property_value': property_value,
                'match_type': criteria.match_type,
            })

        actual_criteria = []
        for criteria in new_rule.caserulecriteria_set.all():
            self.assertTrue(isinstance(criteria.definition, MatchPropertyDefinition))
            actual_criteria.append({
                'property_name': criteria.definition.property_name,
                'property_value': criteria.definition.property_value,
                'match_type': criteria.definition.match_type,
            })

        self.assertEqual(len(expected_criteria), criteria_count)
        self.assertEqual(len(actual_criteria), criteria_count)

        expected_criteria.sort(key=lambda d: d['property_name'])
        actual_criteria.sort(key=lambda d: d['property_name'])
        self.assertEqual(expected_criteria, actual_criteria)

    def assertActionsMigratedCorrectly(self, old_rule, new_rule, update_properties_count):
        self.assertEqual(CaseRuleAction.objects.count(), 1)
        self.assertEqual(UpdateCaseDefinition.objects.count(), 1)
        self.assertEqual(ClosedParentDefinition.objects.count(), 0)
        self.assertEqual(
            old_rule.automaticupdateaction_set.filter(action=AutomaticUpdateAction.ACTION_UPDATE).count(),
            update_properties_count
        )

        properties_to_update = []
        close_case = False
        for action in old_rule.automaticupdateaction_set.all():
            if action.action == AutomaticUpdateAction.ACTION_UPDATE:
                properties_to_update.append({
                    'name': action.property_name,
                    'value': action.property_value,
                    'value_type': action.property_value_type,
                })
            elif action.action == AutomaticUpdateAction.ACTION_CLOSE:
                close_case = True

        new_action = new_rule.caseruleaction_set.all()[0]
        self.assertTrue(isinstance(new_action.definition, UpdateCaseDefinition))
        self.assertEqual(len(new_action.definition.properties_to_update), update_properties_count)
        self.assertEqual(len(properties_to_update), update_properties_count)

        actual_properties_to_update = sorted(
            new_action.definition.properties_to_update,
            key=lambda d: d['name']
        )
        properties_to_update.sort(key=lambda d: d['name'])
        self.assertEqual(actual_properties_to_update, properties_to_update)
        self.assertEqual(new_action.definition.close_case, close_case)

    def assertRuleMigratesCorrectly(self, old_rule, criteria_count, update_properties_count):
        self.assertEqual(CaseRuleCriteria.objects.count(), 0)
        self.assertEqual(MatchPropertyDefinition.objects.count(), 0)
        self.assertEqual(CustomMatchDefinition.objects.count(), 0)
        self.assertEqual(ClosedParentDefinition.objects.count(), 0)
        self.assertEqual(CaseRuleAction.objects.count(), 0)
        self.assertEqual(UpdateCaseDefinition.objects.count(), 0)
        self.assertEqual(CustomActionDefinition.objects.count(), 0)

        old_rule.migrate()
        new_rule = AutomaticUpdateRule.objects.get(pk=old_rule.pk)

        self.assertEqual(old_rule.pk, new_rule.pk)
        self.assertEqual(old_rule.domain, new_rule.domain)
        self.assertEqual(old_rule.name, new_rule.name)
        self.assertEqual(old_rule.case_type, new_rule.case_type)
        self.assertEqual(old_rule.active, new_rule.active)
        self.assertEqual(old_rule.deleted, new_rule.deleted)
        self.assertEqual(old_rule.last_run, new_rule.last_run)
        self.assertEqual(old_rule.filter_on_server_modified, new_rule.filter_on_server_modified)
        self.assertEqual(old_rule.server_modified_boundary, new_rule.server_modified_boundary)
        self.assertFalse(old_rule.migrated)
        self.assertTrue(new_rule.migrated)

        self.assertCriteriaMigratedCorrectly(old_rule, new_rule, criteria_count)
        self.assertActionsMigratedCorrectly(old_rule, new_rule, update_properties_count)

    def test_basic_rule(self):
        rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='basic rule',
            case_type='person',
            active=True,
            deleted=False,
            last_run=None,
            filter_on_server_modified=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        rule.automaticupdateaction_set.create(action=AutomaticUpdateAction.ACTION_CLOSE)
        self.assertRuleMigratesCorrectly(rule, 0, 0)

    def test_update_and_close(self):
        rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='update and close',
            case_type='person',
            active=True,
            deleted=False,
            last_run=None,
            filter_on_server_modified=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        rule.automaticupdateaction_set.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_reason',
            property_value='automatic',
            property_value_type=AutomaticUpdateAction.EXACT,
        )
        rule.automaticupdateaction_set.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='parent_value',
            property_value='parent/value',
            property_value_type=AutomaticUpdateAction.CASE_PROPERTY,
        )
        rule.automaticupdateaction_set.create(action=AutomaticUpdateAction.ACTION_CLOSE)
        self.assertRuleMigratesCorrectly(rule, 0, 2)

    def test_update_only(self):
        rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='update only',
            case_type='person',
            active=True,
            deleted=False,
            last_run=datetime.utcnow(),
            filter_on_server_modified=False,
            server_modified_boundary=None,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        rule.automaticupdateaction_set.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_reason',
            property_value='automatic',
            property_value_type=AutomaticUpdateAction.EXACT,
        )
        rule.automaticupdateaction_set.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='parent_value',
            property_value='parent/value',
            property_value_type=AutomaticUpdateAction.CASE_PROPERTY,
        )
        self.assertRuleMigratesCorrectly(rule, 0, 2)

    def test_all_criteria(self):
        rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='all criteria',
            case_type='person',
            active=True,
            deleted=False,
            last_run=None,
            filter_on_server_modified=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        rule.automaticupdaterulecriteria_set.create(
            property_name='visit_date_1',
            property_value='5',
            match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_BEFORE,
        )
        rule.automaticupdaterulecriteria_set.create(
            property_name='visit_date_2',
            property_value='10',
            match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_AFTER,
        )
        rule.automaticupdaterulecriteria_set.create(
            property_name='property_1',
            property_value='value1',
            match_type=AutomaticUpdateRuleCriteria.MATCH_EQUAL,
        )
        rule.automaticupdaterulecriteria_set.create(
            property_name='parent/property_2',
            property_value='value2',
            match_type=AutomaticUpdateRuleCriteria.MATCH_NOT_EQUAL,
        )
        rule.automaticupdaterulecriteria_set.create(
            property_name='name',
            property_value=None,
            match_type=AutomaticUpdateRuleCriteria.MATCH_HAS_VALUE,
        )
        rule.automaticupdateaction_set.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_reason',
            property_value='automatic',
            property_value_type=AutomaticUpdateAction.EXACT,
        )
        self.assertRuleMigratesCorrectly(rule, 5, 1)

    def test_inactive_rule(self):
        rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='inactive rule',
            case_type='person',
            active=False,
            deleted=False,
            last_run=None,
            filter_on_server_modified=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        rule.automaticupdaterulecriteria_set.create(
            property_name='property1',
            property_value='value1',
            match_type=AutomaticUpdateRuleCriteria.MATCH_EQUAL,
        )
        rule.automaticupdateaction_set.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_reason',
            property_value='automatic',
            property_value_type=AutomaticUpdateAction.EXACT,
        )
        rule.automaticupdateaction_set.create(action=AutomaticUpdateAction.ACTION_CLOSE)
        self.assertRuleMigratesCorrectly(rule, 1, 1)

    def test_deleted_rule(self):
        rule = AutomaticUpdateRule.objects.create(
            domain=self.domain,
            name='inactive rule',
            case_type='person',
            active=True,
            deleted=True,
            last_run=None,
            filter_on_server_modified=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        rule.automaticupdaterulecriteria_set.create(
            property_name='property1',
            property_value='value1',
            match_type=AutomaticUpdateRuleCriteria.MATCH_EQUAL,
        )
        rule.automaticupdateaction_set.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_reason',
            property_value='automatic',
            property_value_type=AutomaticUpdateAction.EXACT,
        )
        rule.automaticupdateaction_set.create(action=AutomaticUpdateAction.ACTION_CLOSE)
        self.assertRuleMigratesCorrectly(rule, 1, 1)
