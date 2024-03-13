from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain

from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule, CaseRuleAction, CaseRuleCriteria,
    ClosedParentDefinition, CustomActionDefinition, CustomMatchDefinition,
    MatchPropertyDefinition, UpdateCaseDefinition
)
from corehq.apps.linked_domain.models import DomainLink
from corehq.apps.linked_domain.updates import update_auto_update_rules
from corehq.apps.linked_domain.tests.test_linked_apps import BaseLinkedDomainTest


# NOTE: The logic being tested is likely duplicating logic elsewhere.
# When you submit a form to create an update rule, that is text translated into a rule
# stored in the database. We are re-inventing the wheel here to turn text into a rule
# to be stored in the database. Ideally, we have a single factory function capable of
# inserting/deleting, and then we can test that factory method.
class TestSyncAutoUpdateRules(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.upstream_domain = 'upstream_domain'
        cls.downstream_domain = 'downstream_domain'

        cls.upstream_domain_obj = create_domain(cls.upstream_domain)
        cls.addClassCleanup(cls.upstream_domain_obj.delete)

        cls.downstream_domain_obj = create_domain(cls.downstream_domain)
        cls.addClassCleanup(cls.downstream_domain_obj.delete)

    def setUp(self):
        super().setUp()
        self.domain_link = DomainLink(master_domain=self.upstream_domain, linked_domain=self.downstream_domain)

    def test_syncs_rule_with_action(self):
        upstream_rule = self._create_rule(domain=self.upstream_domain,
            close_case=True, name='Upstream Rule')

        update_auto_update_rules(self.domain_link)

        downstream_rule = AutomaticUpdateRule.objects.get(upstream_id=upstream_rule.id)
        downstream_action = downstream_rule.caseruleaction_set.all()[0]
        self.assertTrue(downstream_action.definition.close_case)

    def test_can_overwrite_previously_synced_data(self):
        upstream_rule = self._create_rule(domain=self.upstream_domain, name='Upstream Rule')
        downstream_rule = self._create_rule(
            domain=self.downstream_domain, name='Downstream Rule', upstream_id=upstream_rule.id)

        update_auto_update_rules(self.domain_link)

        downstream_rule = AutomaticUpdateRule.objects.get(upstream_id=upstream_rule.id)
        self.assertEqual(downstream_rule.name, 'Upstream Rule')

    def test_does_not_overwrite_based_on_name(self):
        upstream_rule = self._create_rule(domain=self.upstream_domain, name='Upstream Rule')
        # Create Downstream Rule
        self._create_rule(domain=self.downstream_domain, name='Upstream Rule')

        update_auto_update_rules(self.domain_link)

        downstream_rules = AutomaticUpdateRule.objects.filter(
            domain=self.downstream_domain, name='Upstream Rule')
        upstream_ids = [rule.upstream_id for rule in downstream_rules]
        self.assertSetEqual(set(upstream_ids), {None, str(upstream_rule.id)})

    def _create_rule(self, domain='test-domain', name='Test Rule', close_case=True, upstream_id=None):
        rule = AutomaticUpdateRule.objects.create(
            domain=domain,
            name=name,
            active=True,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
            case_type='person',
            filter_on_server_modified=True,
            server_modified_boundary=None,
            upstream_id=upstream_id
        )

        if close_case:
            close_case_definition = UpdateCaseDefinition.objects.create(close_case=True)
            action = CaseRuleAction(rule=rule)
            action.definition = close_case_definition
            action.save()

        return rule


class TestUpdateAutoUpdateRules(BaseLinkedDomainTest):

    def setUp(self):

        test_rules = [
            AutomaticUpdateRule(
                domain=self.domain,
                active=True,
                workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
                name="Norway rule",
                case_type="person",
                filter_on_server_modified=True,
                server_modified_boundary=None
            ),
            AutomaticUpdateRule(
                domain=self.domain,
                active=True,
                workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
                name="Is it hot enough?",
                case_type="person",
                filter_on_server_modified=False,
                server_modified_boundary=2
            ),
            AutomaticUpdateRule(
                domain=self.domain,
                active=False,
                workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
                name="Closed parent case",
                case_type="family_member",
                filter_on_server_modified=True,
                server_modified_boundary=None
            ),
        ]

        test_rules[0].save()
        test_rules[1].save()
        test_rules[2].save()

        # Create test rule criterias
        definition = MatchPropertyDefinition.objects.create(
            property_name="place",
            property_value="Norway",
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        criteria = CaseRuleCriteria(rule=test_rules[0])
        criteria.definition = definition
        criteria.save()

        definition = MatchPropertyDefinition.objects.create(
            property_name="temperature",
            property_value="96",
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        criteria = CaseRuleCriteria(rule=test_rules[1])
        criteria.definition = definition
        criteria.save()

        definition = CustomMatchDefinition.objects.create(
            name="COVID_US_ASSOCIATED_USER_CASES",
        )
        criteria = CaseRuleCriteria(rule=test_rules[0])
        criteria.definition = definition
        criteria.save()

        definition = ClosedParentDefinition.objects.create()
        criteria = CaseRuleCriteria(rule=test_rules[2])
        criteria.definition = definition
        criteria.save()

        # Create test rule actions
        definition = UpdateCaseDefinition(close_case=True)
        definition.save()
        action = CaseRuleAction(rule=test_rules[0])
        action.definition = definition
        action.save()

        definition = UpdateCaseDefinition(close_case=False)
        test_properties = []
        test_properties.append(
            UpdateCaseDefinition.PropertyDefinition(
                name="hot_enough",
                value_type="EXACT",
                value="true",
            ))
        test_properties.append(
            UpdateCaseDefinition.PropertyDefinition(
                name="territory_hot_enough",
                value_type="CASE_PROPERTY",
                value="current_territory",
            ))
        definition.set_properties_to_update(test_properties)
        definition.save()

        action = CaseRuleAction(rule=test_rules[1])
        action.definition = definition
        action.save()

        definition = CustomActionDefinition.objects.create(
            name="COVID_US_CLOSE_CASES_ASSIGNED_CHECKIN",
        )

        action = CaseRuleAction(rule=test_rules[1])
        action.definition = definition
        action.save()

    def test_update_auto_update_rules(self):
        self.assertFalse(AutomaticUpdateRule.by_domain(domain=self.linked_domain,
            workflow="CASE_UPDATE").exists())

        update_auto_update_rules(self.domain_link)

        linked_domain_rules = AutomaticUpdateRule.by_domain(self.linked_domain, active_only=False,
                workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        self.assertEqual(3, linked_domain_rules.count())

        for rule in linked_domain_rules:
            self.assertTrue(rule.name in ["Norway rule", "Is it hot enough?", "Closed parent case"])
            if(rule.name == "Closed parent case"):
                self.assertEqual(rule.case_type, "family_member")
            else:
                self.assertEqual(rule.case_type, "person")
            if(rule.name == "Is it hot enough?"):
                self.assertFalse(rule.filter_on_server_modified)
                self.assertEqual(2, rule.server_modified_boundary)
            else:
                self.assertTrue(rule.filter_on_server_modified)
                self.assertFalse(rule.server_modified_boundary)

            caseRuleCriterias = CaseRuleCriteria.objects.filter(rule=rule)
            if(rule.name == "Is it hot enough?"):
                criteria = caseRuleCriterias.first()
                self.assertEqual(criteria.match_property_definition.property_name, "temperature")
                self.assertEqual(criteria.match_property_definition.property_value, "96")
                self.assertEqual(criteria.match_property_definition.match_type,
                    MatchPropertyDefinition.MATCH_EQUAL)
                self.assertFalse(criteria.closed_parent_definition)
            elif(rule.name == "Norway rule"):
                self.assertEqual(2, caseRuleCriterias.count())
                for criteria in caseRuleCriterias:
                    self.assertTrue(criteria.match_property_definition or criteria.custom_match_definition)
                    if(criteria.match_property_definition is not None):
                        self.assertEqual(criteria.match_property_definition.property_value, "Norway")
                    elif(criteria.custom_match_definition is not None):
                        self.assertEqual(criteria.custom_match_definition.name,
                            "COVID_US_ASSOCIATED_USER_CASES")
            elif(rule.name == "Closed parent case"):
                criteria = caseRuleCriterias.first()
                self.assertTrue(criteria.closed_parent_definition)

            caseRuleActions = CaseRuleAction.objects.filter(rule=rule)
            if(rule.name == "Norway rule"):
                action = caseRuleActions.first()
                self.assertEqual(action.update_case_definition.close_case, True)
            if(rule.name == "Is it hot enough?"):
                self.assertEqual(2, caseRuleActions.count())
                for action in caseRuleActions:
                    if(action.update_case_definition is not None):
                        self.assertEqual(2, len(action.update_case_definition.properties_to_update))
                        for property in action.update_case_definition.properties_to_update:
                            self.assertTrue(property['name'] in ["hot_enough", "territory_hot_enough"])
                            if(property['name'] == "hot_enough"):
                                self.assertEqual(property['value_type'], "EXACT")
                            elif(property['name'] == "territory_hot_enough"):
                                self.assertEqual(property['value'], "current_territory")
                    elif(action.custom_action_definition is not None):
                        self.assertEqual(action.custom_action_definition.name,
                        "COVID_US_CLOSE_CASES_ASSIGNED_CHECKIN")
