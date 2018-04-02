from __future__ import absolute_import
from __future__ import unicode_literals
from contextlib import contextmanager

from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.signals import case_post_save
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    AutomaticUpdateRuleCriteria,
    AutomaticUpdateAction, AUTO_UPDATE_XMLNS,
    MatchPropertyDefinition,
    ClosedParentDefinition,
    CustomMatchDefinition,
    UpdateCaseDefinition,
    CustomActionDefinition,
    CaseRuleCriteria,
    CaseRuleAction,
    CaseRuleSubmission,
    CaseRuleActionResult,
    DomainCaseRuleRun,
    CaseRuleUndoer,
)
from corehq.apps.data_interfaces.tasks import run_case_update_rules_for_domain
from corehq.apps.domain.models import Domain
from datetime import datetime, date

from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors, FormAccessors
from corehq.form_processor.tests.utils import (run_with_all_backends, FormProcessorTestUtils,
    set_case_property_directly)
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.form_processor.signals import sql_case_post_save

from corehq.util.test_utils import set_parent_case as set_actual_parent_case, update_case
from django.test import TestCase, override_settings
from mock import patch

from corehq.util.context_managers import drop_connected_signals
from toggle.shortcuts import update_toggle_cache
from corehq.toggles import NAMESPACE_DOMAIN, AUTO_CASE_UPDATE_ENHANCEMENTS, RUN_AUTO_CASE_UPDATES_ON_SAVE
from corehq.apps import hqcase


class AutomaticCaseUpdateTest(TestCase):

    def setUp(self):
        super(AutomaticCaseUpdateTest, self).setUp()
        self.domain = 'auto-update-test'
        self.domain_object = Domain(name=self.domain)
        self.domain_object.save()
        update_toggle_cache(AUTO_CASE_UPDATE_ENHANCEMENTS.slug, self.domain, True, NAMESPACE_DOMAIN)
        update_toggle_cache(RUN_AUTO_CASE_UPDATES_ON_SAVE.slug, self.domain, True, NAMESPACE_DOMAIN)
        self.case_db = CaseAccessors(self.domain)
        self.factory = CaseFactory(self.domain)
        self.rule = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule',
            case_type='test-case-type',
            active=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        self.rule.save()
        AutomaticUpdateRuleCriteria.objects.create(
            property_name='last_visit_date',
            property_value='30',
            match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_AFTER,
            rule=self.rule,
        )
        AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_flag',
            property_value='Y',
            rule=self.rule,
        )

        self.rule2 = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule-2',
            case_type='test-case-type-2',
            active=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        self.rule2.save()
        AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_CLOSE,
            rule=self.rule2,
        )

        self.rule3 = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule-3',
            case_type='test-case-type-2',
            active=True,
            server_modified_boundary=50,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        self.rule3.save()
        AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_CLOSE,
            rule=self.rule3,
        )

        self.rule4 = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule-4',
            case_type='test-case-type',
            active=True,
            server_modified_boundary=30,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        self.rule4.save()
        AutomaticUpdateRuleCriteria.objects.create(
            property_name='last_visit_date',
            property_value='40',
            match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_AFTER,
            rule=self.rule4,
        )
        AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='update_flag',
            property_value='C',
            rule=self.rule4,
        )
        AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_CLOSE,
            rule=self.rule4,
        )
        self.rule5 = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule-5',
            case_type='test-case-type-3',
            active=True,
            filter_on_server_modified=False,
            workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
        )
        self.rule5.save()
        AutomaticUpdateRuleCriteria.objects.create(
            property_name='name',
            property_value='signal',
            match_type=AutomaticUpdateRuleCriteria.MATCH_EQUAL,
            rule=self.rule5,
        )
        AutomaticUpdateAction.objects.create(
            action=AutomaticUpdateAction.ACTION_UPDATE,
            property_name='after_save',
            property_value='updated',
            rule=self.rule5,
        )

        self.rule = self.rule.migrate()
        self.rule2 = self.rule2.migrate()
        self.rule3 = self.rule3.migrate()
        self.rule4 = self.rule4.migrate()
        self.rule5 = self.rule5.migrate()

        with drop_connected_signals(case_post_save):
            case = self.factory.create_case(case_type='test-case-type')
        self.case_id = case.case_id

    def tearDown(self):
        DomainCaseRuleRun.objects.all().delete()
        CaseRuleSubmission.objects.all().delete()
        AutomaticUpdateRuleCriteria.objects.all().delete()
        AutomaticUpdateAction.objects.all().delete()
        CaseRuleCriteria.objects.all().delete()
        MatchPropertyDefinition.objects.all().delete()
        CaseRuleAction.objects.all().delete()
        UpdateCaseDefinition.objects.all().delete()
        AutomaticUpdateRule.objects.all().delete()
        FormProcessorTestUtils.delete_all_cases(self.domain)
        self.domain_object.delete()
        super(AutomaticCaseUpdateTest, self).tearDown()

    def _get_case(self):
        return self.case_db.get_case(self.case_id)

    def _assert_case_revision(self, rev_number, last_modified, expect_modified=False):
        if should_use_sql_backend(self.domain):
            modified_on = CaseAccessorSQL.get_last_modified_dates(self.domain, [self.case_id])[self.case_id]
            has_been_modified = modified_on != last_modified
            self.assertEqual(expect_modified, has_been_modified)
        else:
            doc = self._get_case()
            self.assertTrue(doc['_rev'].startswith('%s-' % rev_number))

    @run_with_all_backends
    def test_rule(self):
        now = datetime(2015, 10, 22, 0, 0)
        with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.get_case_ids') as case_ids_patch:
            case_ids_patch.return_value = [self.case_id]

            # No update: both dates are 27 days away
            last_modified = datetime(2015, 9, 25, 12, 0)
            _update_case(self.domain, self.case_id, last_modified, date(2015, 9, 25))
            self._assert_case_revision(2, last_modified)
            run_case_update_rules_for_domain(self.domain, now=now)
            self._assert_case_revision(2, last_modified)

            # No update: server_modified_on is 32 days away but last_visit_date is 27 days away
            last_modified = datetime(2015, 9, 20, 12, 0)
            _update_case(self.domain, self.case_id, last_modified, date(2015, 9, 25))
            self._assert_case_revision(3, last_modified)
            run_case_update_rules_for_domain(self.domain, now=now)
            self._assert_case_revision(3, last_modified)

            # No update: last_visit_date is 32 days away but server_modified_on is 27 days away
            last_modified = datetime(2015, 9, 25, 12, 0)
            _update_case(self.domain, self.case_id, last_modified, date(2015, 9, 20))
            self._assert_case_revision(4, last_modified)
            run_case_update_rules_for_domain(self.domain, now=now)
            self._assert_case_revision(4, last_modified)

            # Perform update: both dates are 32 days away
            last_modified = datetime(2015, 9, 20, 12, 0)
            _update_case(self.domain, self.case_id, last_modified, date(2015, 9, 20))
            self._assert_case_revision(5, last_modified)
            with drop_connected_signals(case_post_save):
                run_case_update_rules_for_domain(self.domain, now=now)
            self._assert_case_revision(6, last_modified, True)

            case = self._get_case()
            self.assertEqual(case.get_case_property('update_flag'), 'Y')

            # No update: case state matches final state
            _update_case(self.domain, self.case_id, last_modified, date(2015, 9, 20))
            self._assert_case_revision(7, last_modified)
            with drop_connected_signals(case_post_save):
                run_case_update_rules_for_domain(self.domain, now=now)
            self._assert_case_revision(7, last_modified)

            # Perform update: case closed because date is 42 days away
            _update_case(self.domain, self.case_id, last_modified, date(2015, 9, 10))
            with drop_connected_signals(case_post_save):
                run_case_update_rules_for_domain(self.domain, now=now)

            case = self._get_case()
            self.assertEqual(case.get_case_property('update_flag'), 'C')
            self.assertEqual(case.closed, True)

    @run_with_all_backends
    def test_match_days_after(self):
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='last_visit_date',
                property_value='30',
                match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
            )
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2015-12-30')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2015-12-03')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2015-12-02')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2015-11-01')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_match_days_before(self):
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='last_visit_date',
                property_value='-30',
                match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
            )
            # When the case property doesn't exist, it should not match
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2015-10-01')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2016-01-02')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2016-01-31')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2016-02-01')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2016-03-01')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_match_equal(self):
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property1',
                property_value='value1',
                match_type=MatchPropertyDefinition.MATCH_EQUAL,
            )
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property1', 'x')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property1', 'value1')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_match_not_equal(self):
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property2',
                property_value='value2',
                match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
            )
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property2', 'value2')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property2', 'x')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_date_case_properties_for_equality(self):
        """
        Date case properties are automatically converted from string to date
        when fetching from the db, so here we want to make sure this doesn't
        interfere with our ability to compare dates for equality.
        """
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property1',
                property_value='2016-02-24',
                match_type=MatchPropertyDefinition.MATCH_EQUAL,
            )

            set_case_property_directly(case, 'property1', '2016-02-24')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property1', '2016-02-25')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_date_case_properties_for_inequality(self):
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property1',
                property_value='2016-02-24',
                match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
            )

            set_case_property_directly(case, 'property1', '2016-02-24')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property1', '2016-02-25')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_match_has_value(self):
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property3',
                match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
            )
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property3', 'x')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property3', '')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_and_criteria(self):
        with _with_case(self.domain, 'test-case-type-2', datetime(2015, 1, 1)) as case:

            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='last_visit_date',
                property_value='30',
                match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
            )
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property1',
                property_value='value1',
                match_type=MatchPropertyDefinition.MATCH_EQUAL,
            )
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property2',
                property_value='value2',
                match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
            )
            self.rule2.add_criteria(
                MatchPropertyDefinition,
                property_name='property3',
                match_type=MatchPropertyDefinition.MATCH_HAS_VALUE,
            )

            set_case_property_directly(case, 'last_visit_date', '2015-11-01')
            set_case_property_directly(case, 'property1', 'value1')
            set_case_property_directly(case, 'property2', 'x')
            set_case_property_directly(case, 'property3', 'x')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2015-12-30')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'last_visit_date', '2015-11-01')
            set_case_property_directly(case, 'property1', 'x')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property1', 'value1')
            set_case_property_directly(case, 'property2', 'value2')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property2', 'x')
            set_case_property_directly(case, 'property3', '')
            self.assertFalse(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

            set_case_property_directly(case, 'property3', 'x')
            self.assertTrue(self.rule2.criteria_match(case, datetime(2016, 1, 1)))

    def test_get_rules_from_domain(self):
        rules = AutomaticUpdateRule.by_domain(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)

        expected_case_types = ['test-case-type', 'test-case-type-2', 'test-case-type-3']
        actual_case_types = list(rules_by_case_type)
        self.assertEqual(set(expected_case_types), set(actual_case_types))

        expected_rule_ids = [self.rule.pk, self.rule4.pk]
        actual_rule_ids = [rule.pk for rule in rules_by_case_type['test-case-type']]
        self.assertEqual(set(expected_rule_ids), set(actual_rule_ids))

        expected_rule_ids = [self.rule2.pk, self.rule3.pk]
        actual_rule_ids = [rule.pk for rule in rules_by_case_type['test-case-type-2']]
        self.assertEqual(set(expected_rule_ids), set(actual_rule_ids))

        expected_rule_ids = [self.rule5.pk]
        actual_rule_ids = [rule.pk for rule in rules_by_case_type['test-case-type-3']]
        self.assertEqual(set(expected_rule_ids), set(actual_rule_ids))

    def test_boundary_date(self):
        rules = AutomaticUpdateRule.by_domain(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)

        boundary_date = AutomaticUpdateRule.get_boundary_date(
            rules_by_case_type['test-case-type'], datetime(2016, 1, 1))
        self.assertEqual(boundary_date, datetime(2015, 12, 2))

        boundary_date = AutomaticUpdateRule.get_boundary_date(
            rules_by_case_type['test-case-type-2'], datetime(2016, 1, 1))
        self.assertEqual(boundary_date, datetime(2015, 12, 2))

    @run_with_all_backends
    def test_parent_cases(self):
        with _with_case(self.domain, 'test-child-case-type', datetime(2016, 1, 1)) as child, \
                _with_case(self.domain, 'test-parent-case-type', datetime(2016, 1, 1), case_name='abc') as parent:

            # Set the parent case relationship
            child = set_parent_case(self.domain, child, parent)

            # Create a rule that references parent/name which should match
            rule = AutomaticUpdateRule(
                domain=self.domain,
                name='test-parent-rule',
                case_type='test-child-case-type',
                active=True,
                server_modified_boundary=30,
                workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
            )
            rule.save()
            self.addCleanup(rule.delete)
            AutomaticUpdateRuleCriteria.objects.create(
                property_name='parent/name',
                property_value='abc',
                match_type=AutomaticUpdateRuleCriteria.MATCH_EQUAL,
                rule=rule,
            )
            AutomaticUpdateAction.objects.create(
                action=AutomaticUpdateAction.ACTION_UPDATE,
                property_name='parent/update_flag',
                property_value='P',
                rule=rule,
            )
            AutomaticUpdateAction.objects.create(
                action=AutomaticUpdateAction.ACTION_UPDATE,
                property_name='parent_name',
                property_value='parent/name',
                property_value_type=AutomaticUpdateAction.CASE_PROPERTY,
                rule=rule,
            )
            rule = rule.migrate()

            # rule should match on parent case property and update parent case
            rule.run_rule(child, datetime(2016, 3, 1))
            updated_parent = self.case_db.get_case(parent.case_id)
            updated_child = self.case_db.get_case(child.case_id)
            self.assertEqual(updated_parent.get_case_property('update_flag'), 'P')
            self.assertEqual(updated_child.get_case_property('parent_name'), 'abc')

            # Update the rule to match on a different name and now it shouldn't match
            rule.delete_criteria()
            rule.add_criteria(
                MatchPropertyDefinition,
                property_name='parent/name',
                property_value='def',
                match_type=MatchPropertyDefinition.MATCH_EQUAL,
            )
            # reset memoized caches
            rule = AutomaticUpdateRule.objects.get(pk=rule.pk)

            self.assertFalse(rule.criteria_match(child, datetime(2016, 3, 1)))

    @run_with_all_backends
    def test_no_server_boundary(self):
        with _with_case(self.domain, 'test-case-type-3', datetime(2016, 1, 1), case_name='signal') as case:
            # no filtering on server modified date so same day matches
            self.assertTrue(self.rule5.criteria_match(case, datetime(2016, 1, 1)))

    @run_with_all_backends
    def test_run_on_save(self):
        with _with_case(self.domain, 'test-case-type-3', datetime(2016, 1, 1), case_name='signal') as case:
            with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.run_rule') as apply:
                # property is updated after save signal (case update used to force save)
                update_case(self.domain, case.case_id, {})
                apply.assert_called_once()

    @run_with_all_backends
    def test_early_task_exit(self):
        with _with_case(self.domain, 'test-case-type-3', datetime(2016, 1, 1), case_name='signal') as case:
            with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.run_rule') as apply:
                hqcase.utils.update_case(case.domain, case.case_id, case_properties={}, xmlns=AUTO_UPDATE_XMLNS)
                apply.assert_not_called()


@contextmanager
def _with_case(domain, case_type, last_modified, **kwargs):
    with drop_connected_signals(case_post_save), drop_connected_signals(sql_case_post_save):
        case = CaseFactory(domain).create_case(case_type=case_type, **kwargs)

    _update_case(domain, case.case_id, last_modified)
    accessors = CaseAccessors(domain)
    case = accessors.get_case(case.case_id)
    try:
        yield case
    finally:
        if should_use_sql_backend(domain):
            CaseAccessorSQL.hard_delete_cases(domain, [case.case_id])
        else:
            case.delete()


def _save_case(domain, case):
    if should_use_sql_backend(domain):
        CaseAccessorSQL.save_case(case)
    else:
        # can't call case.save() since it overrides the server_modified_on property
        CommCareCase.get_db().save_doc(case.to_json())


def _update_case(domain, case_id, server_modified_on, last_visit_date=None):
    accessors = CaseAccessors(domain)
    case = accessors.get_case(case_id)
    case.server_modified_on = server_modified_on
    if last_visit_date:
        set_case_property_directly(case, 'last_visit_date', last_visit_date.strftime('%Y-%m-%d'))
    _save_case(domain, case)


def set_parent_case(domain, child_case, parent_case, relationship='child', identifier='parent'):
    server_modified_on = child_case.server_modified_on
    set_actual_parent_case(domain, child_case, parent_case, relationship=relationship, identifier=identifier)

    child_case = CaseAccessors(domain).get_case(child_case.case_id)
    child_case.server_modified_on = server_modified_on
    _save_case(domain, child_case)
    return CaseAccessors(domain).get_case(child_case.case_id)


def dummy_custom_match_function(case, now):
    pass


def dummy_custom_action(case, rule):
    pass


def _create_empty_rule(domain, case_type='person', active=True, deleted=False):
    return AutomaticUpdateRule.objects.create(
        domain=domain,
        name='test',
        case_type=case_type,
        active=active,
        deleted=deleted,
        filter_on_server_modified=False,
        server_modified_boundary=None,
        migrated=True,
        workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
    )


class BaseCaseRuleTest(TestCase):
    domain = 'case-rule-test'

    def tearDown(self):
        for rule in AutomaticUpdateRule.objects.filter(domain=self.domain):
            rule.hard_delete()

        DomainCaseRuleRun.objects.filter(domain=self.domain).delete()


class CaseRuleCriteriaTest(BaseCaseRuleTest):

    @run_with_all_backends
    def test_match_case_type(self):
        rule = _create_empty_rule(self.domain)

        with _with_case(self.domain, 'child', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_server_modified(self):
        rule = _create_empty_rule(self.domain)
        rule.filter_on_server_modified = True
        rule.server_modified_boundary = 10
        rule.save()

        with _with_case(self.domain, 'person', datetime(2017, 4, 25)) as case:
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 26)))

        with _with_case(self.domain, 'person', datetime(2017, 4, 15)) as case:
            self.assertTrue(rule.criteria_match(case, datetime(2017, 4, 26)))

    @run_with_all_backends
    def test_case_property_equal(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='result',
            property_value='negative',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'x'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'negative'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_case_property_not_equal(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='result',
            property_value='negative',
            match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'x'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'negative'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_dates_case_properties_for_equality_inequality(self):
        """
        Date case properties are automatically converted from string to date
        when fetching from the db, so here we want to make sure this doesn't
        interfere with our ability to compare dates for equality.
        """
        rule1 = _create_empty_rule(self.domain)
        rule1.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit',
            property_value='2017-03-01',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        rule2 = _create_empty_rule(self.domain)
        rule2.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit',
            property_value='2017-03-01',
            match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule1.criteria_match(case, datetime.utcnow()))
            self.assertTrue(rule2.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'last_visit': '2017-03-01'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule1.criteria_match(case, datetime.utcnow()))
            self.assertFalse(rule2.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'last_visit': '2017-03-02'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule1.criteria_match(case, datetime.utcnow()))
            self.assertTrue(rule2.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_case_property_has_value(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='result',
            match_type=MatchPropertyDefinition.MATCH_HAS_VALUE
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'x'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': ''})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_case_property_has_no_value(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='result',
            match_type=MatchPropertyDefinition.MATCH_HAS_NO_VALUE
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'x'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': ''})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_date_case_property_before(self):
        rule1 = _create_empty_rule(self.domain)
        rule1.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='-5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
        )

        rule2 = _create_empty_rule(self.domain)
        rule2.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='0',
            match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
        )

        rule3 = _create_empty_rule(self.domain)
        rule3.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule1.criteria_match(case, datetime.utcnow()))
            self.assertFalse(rule2.criteria_match(case, datetime.utcnow()))
            self.assertFalse(rule3.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'last_visit_date': '2017-01-15'})
            case = CaseAccessors(self.domain).get_case(case.case_id)

            self.assertTrue(rule1.criteria_match(case, datetime(2017, 1, 5)))
            self.assertFalse(rule1.criteria_match(case, datetime(2017, 1, 10)))
            self.assertFalse(rule1.criteria_match(case, datetime(2017, 1, 15)))

            self.assertTrue(rule2.criteria_match(case, datetime(2017, 1, 10)))
            self.assertFalse(rule2.criteria_match(case, datetime(2017, 1, 15)))
            self.assertFalse(rule2.criteria_match(case, datetime(2017, 1, 20)))

            self.assertTrue(rule3.criteria_match(case, datetime(2017, 1, 15)))
            self.assertFalse(rule3.criteria_match(case, datetime(2017, 1, 20)))
            self.assertFalse(rule3.criteria_match(case, datetime(2017, 1, 25)))

    @run_with_all_backends
    def test_date_case_property_after(self):
        rule1 = _create_empty_rule(self.domain)
        rule1.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='-5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
        )

        rule2 = _create_empty_rule(self.domain)
        rule2.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='0',
            match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
        )

        rule3 = _create_empty_rule(self.domain)
        rule3.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule1.criteria_match(case, datetime.utcnow()))
            self.assertFalse(rule2.criteria_match(case, datetime.utcnow()))
            self.assertFalse(rule3.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'last_visit_date': '2017-01-15'})
            case = CaseAccessors(self.domain).get_case(case.case_id)

            self.assertFalse(rule1.criteria_match(case, datetime(2017, 1, 5)))
            self.assertTrue(rule1.criteria_match(case, datetime(2017, 1, 10)))
            self.assertTrue(rule1.criteria_match(case, datetime(2017, 1, 15)))

            self.assertFalse(rule2.criteria_match(case, datetime(2017, 1, 10)))
            self.assertTrue(rule2.criteria_match(case, datetime(2017, 1, 15)))
            self.assertTrue(rule2.criteria_match(case, datetime(2017, 1, 20)))

            self.assertFalse(rule3.criteria_match(case, datetime(2017, 1, 15)))
            self.assertTrue(rule3.criteria_match(case, datetime(2017, 1, 20)))
            self.assertTrue(rule3.criteria_match(case, datetime(2017, 1, 25)))

    @run_with_all_backends
    def test_parent_case_reference(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='parent/result',
            property_value='negative',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as parent:

            hqcase.utils.update_case(self.domain, parent.case_id, case_properties={'result': 'negative'})
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

            child = set_parent_case(self.domain, child, parent)
            self.assertTrue(rule.criteria_match(child, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, parent.case_id, case_properties={'result': 'x'})
            # reset memoized cache
            child = CaseAccessors(self.domain).get_case(child.case_id)
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

    @run_with_all_backends
    def test_host_case_reference(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='host/result',
            property_value='negative',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as host:

            hqcase.utils.update_case(self.domain, host.case_id, case_properties={'result': 'negative'})
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

            child = set_parent_case(self.domain, child, host, relationship='extension', identifier='host')
            self.assertTrue(rule.criteria_match(child, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, host.case_id, case_properties={'result': 'x'})
            # reset memoized cache
            child = CaseAccessors(self.domain).get_case(child.case_id)
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

    @run_with_all_backends
    def test_parent_case_closed(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(ClosedParentDefinition)

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as parent:

            child = set_parent_case(self.domain, child, parent)
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, parent.case_id, close=True)
            # reset memoized cache
            child = CaseAccessors(self.domain).get_case(child.case_id)
            self.assertTrue(rule.criteria_match(child, datetime.utcnow()))

    @run_with_all_backends
    @override_settings(
        AVAILABLE_CUSTOM_RULE_CRITERIA={
            'CUSTOM_CRITERIA_TEST':
                'corehq.apps.data_interfaces.tests.test_auto_case_updates.dummy_custom_match_function',
        }
    )
    def test_custom_match(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(CustomMatchDefinition, name='CUSTOM_CRITERIA_TEST')

        with _with_case(self.domain, 'person', datetime.utcnow()) as case, \
                patch('corehq.apps.data_interfaces.tests.test_auto_case_updates.dummy_custom_match_function') as p:

            now = datetime.utcnow()
            p.return_value = True
            p.assert_not_called()
            self.assertTrue(rule.criteria_match(case, now))
            p.assert_called_once_with(case, now)

        with _with_case(self.domain, 'person', datetime.utcnow()) as case, \
                patch('corehq.apps.data_interfaces.tests.test_auto_case_updates.dummy_custom_match_function') as p:

            now = datetime.utcnow()
            p.return_value = False
            p.assert_not_called()
            self.assertFalse(rule.criteria_match(case, now))
            p.assert_called_once_with(case, now)

    @run_with_all_backends
    def test_multiple_criteria(self):
        rule = _create_empty_rule(self.domain)

        rule.filter_on_server_modified = True
        rule.server_modified_boundary = 10
        rule.save()

        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='abc',
            property_value='123',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='def',
            property_value='456',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            case.server_modified_on = datetime(2017, 4, 1)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 10)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 1)
            set_case_property_directly(case, 'abc', '123x')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 1)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456x')
            _save_case(self.domain, case)
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 1)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime(2017, 4, 15)))


class CaseRuleActionsTest(BaseCaseRuleTest):

    def assertActionResult(self, rule, submission_count, result=None, expected_result=None):
        self.assertEqual(CaseRuleSubmission.objects.count(), submission_count)

        for submission in CaseRuleSubmission.objects.all():
            self.assertEqual(submission.domain, self.domain)
            self.assertEqual(submission.rule_id, rule.pk)

        if result and expected_result:
            self.assertEqual(result, expected_result)

    @run_with_all_backends
    def test_update_only(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result1',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
            UpdateCaseDefinition.PropertyDefinition(
                name='result2',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='def',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertActionResult(rule, 0)

            result = rule.run_actions_when_case_matches(case)
            case = CaseAccessors(self.domain).get_case(case.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertEqual(case.get_case_property('result1'), 'abc')
            self.assertEqual(case.get_case_property('result2'), 'def')
            self.assertFalse(case.closed)

    @run_with_all_backends
    def test_close_only(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=True)

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertActionResult(rule, 0)

            dynamic_properties_before = case.dynamic_case_properties()
            result = rule.run_actions_when_case_matches(case)
            case = CaseAccessors(self.domain).get_case(case.case_id)
            dynamic_properties_after = case.dynamic_case_properties()

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_closes=1))
            self.assertTrue(case.closed)
            self.assertEqual(dynamic_properties_before, dynamic_properties_after)

    @run_with_all_backends
    def test_update_parent(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='parent/result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as parent:

            child = set_parent_case(self.domain, child, parent)
            child_dynamic_properties_before = child.dynamic_case_properties()

            self.assertActionResult(rule, 0)
            result = rule.run_actions_when_case_matches(child)
            child = CaseAccessors(self.domain).get_case(child.case_id)
            parent = CaseAccessors(self.domain).get_case(parent.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_related_updates=1))
            self.assertEqual(parent.get_case_property('result'), 'abc')
            self.assertEqual(child.dynamic_case_properties(), child_dynamic_properties_before)

            self.assertFalse(child.closed)
            self.assertFalse(parent.closed)

    @run_with_all_backends
    def test_update_host(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='host/result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as host:

            child = set_parent_case(self.domain, child, host, relationship='extension', identifier='host')
            child_dynamic_properties_before = child.dynamic_case_properties()

            self.assertActionResult(rule, 0)
            result = rule.run_actions_when_case_matches(child)
            child = CaseAccessors(self.domain).get_case(child.case_id)
            host = CaseAccessors(self.domain).get_case(host.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_related_updates=1))
            self.assertEqual(host.get_case_property('result'), 'abc')
            self.assertEqual(child.dynamic_case_properties(), child_dynamic_properties_before)

            self.assertFalse(child.closed)
            self.assertFalse(host.closed)

    @run_with_all_backends
    def test_update_from_other_case_property(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_CASE_PROPERTY,
                value='other_result',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertActionResult(rule, 0)

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'other_result': 'xyz'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertNotIn('result', case.dynamic_case_properties())

            result = rule.run_actions_when_case_matches(case)
            case = CaseAccessors(self.domain).get_case(case.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertEqual(case.get_case_property('result'), 'xyz')
            self.assertEqual(case.get_case_property('other_result'), 'xyz')
            self.assertFalse(case.closed)

    @run_with_all_backends
    def test_update_from_parent_case_property(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_CASE_PROPERTY,
                value='parent/result',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as parent:
            self.assertActionResult(rule, 0)

            child = set_parent_case(self.domain, child, parent)
            hqcase.utils.update_case(self.domain, parent.case_id, case_properties={'result': 'xyz'})
            parent = CaseAccessors(self.domain).get_case(parent.case_id)
            self.assertNotIn('result', child.dynamic_case_properties())
            parent_case_properties_before = parent.dynamic_case_properties()

            result = rule.run_actions_when_case_matches(child)
            child = CaseAccessors(self.domain).get_case(child.case_id)
            parent = CaseAccessors(self.domain).get_case(parent.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertEqual(child.get_case_property('result'), 'xyz')
            self.assertEqual(parent.dynamic_case_properties(), parent_case_properties_before)
            self.assertFalse(child.closed)
            self.assertFalse(parent.closed)

    @run_with_all_backends
    def test_no_update(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='xyz',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertActionResult(rule, 0)

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'xyz'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            server_modified_before = case.server_modified_on
            self.assertEqual(case.get_case_property('result'), 'xyz')

            result = rule.run_actions_when_case_matches(case)
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(case.server_modified_on, server_modified_before)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 0, result, CaseRuleActionResult())
            self.assertFalse(case.closed)

    @run_with_all_backends
    def test_update_and_close(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=True)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
            UpdateCaseDefinition.PropertyDefinition(
                name='parent/result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='def',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as parent:

            self.assertActionResult(rule, 0)

            child = set_parent_case(self.domain, child, parent)
            result = rule.run_actions_when_case_matches(child)

            child = CaseAccessors(self.domain).get_case(child.case_id)
            parent = CaseAccessors(self.domain).get_case(parent.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 2, result,
                CaseRuleActionResult(num_updates=1, num_closes=1, num_related_updates=1))

            self.assertEqual(child.get_case_property('result'), 'abc')
            self.assertEqual(parent.get_case_property('result'), 'def')

            self.assertTrue(child.closed)
            self.assertFalse(parent.closed)

    @run_with_all_backends
    def test_undo(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=True)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
            UpdateCaseDefinition.PropertyDefinition(
                name='parent/result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='def',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as parent:

            self.assertActionResult(rule, 0)

            child = set_parent_case(self.domain, child, parent)
            result = rule.run_actions_when_case_matches(child)

            child = CaseAccessors(self.domain).get_case(child.case_id)
            parent = CaseAccessors(self.domain).get_case(parent.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 2, result,
                CaseRuleActionResult(num_updates=1, num_closes=1, num_related_updates=1))

            self.assertEqual(child.get_case_property('result'), 'abc')
            self.assertEqual(parent.get_case_property('result'), 'def')

            self.assertTrue(child.closed)
            self.assertFalse(parent.closed)

            undoer = CaseRuleUndoer(self.domain, rule_id=rule.pk)
            result = undoer.bulk_undo()
            self.assertEqual(result, {
                'processed': 2,
                'skipped': 0,
                'archived': 2,
            })

            child = CaseAccessors(self.domain).get_case(child.case_id)
            parent = CaseAccessors(self.domain).get_case(parent.case_id)

            self.assertNotIn('result', child.dynamic_case_properties())
            self.assertNotIn('result', parent.dynamic_case_properties())

            self.assertFalse(child.closed)
            self.assertFalse(parent.closed)

            self.assertEqual(CaseRuleSubmission.objects.filter(domain=self.domain).count(), 2)
            self.assertEqual(CaseRuleSubmission.objects.filter(domain=self.domain, archived=True).count(), 2)

            form_ids = CaseRuleSubmission.objects.filter(domain=self.domain).values_list('form_id', flat=True)
            for form in FormAccessors(self.domain).iter_forms(form_ids):
                self.assertTrue(form.is_archived)

    @run_with_all_backends
    @override_settings(
        AVAILABLE_CUSTOM_RULE_ACTIONS={
            'CUSTOM_ACTION_TEST':
                'corehq.apps.data_interfaces.tests.test_auto_case_updates.dummy_custom_action',
        }
    )
    def test_multiple_actions(self):
        rule = _create_empty_rule(self.domain)
        rule.add_action(UpdateCaseDefinition, close_case=True)
        rule.add_action(CustomActionDefinition, name='CUSTOM_ACTION_TEST')

        with _with_case(self.domain, 'person', datetime.utcnow()) as case, \
                patch('corehq.apps.data_interfaces.tests.test_auto_case_updates.dummy_custom_action') as p:
            self.assertActionResult(rule, 0)

            p.return_value = CaseRuleActionResult(num_related_updates=1)
            result = rule.run_actions_when_case_matches(case)
            p.assert_called_once_with(case, rule)
            case = CaseAccessors(self.domain).get_case(case.case_id)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_closes=1, num_related_updates=1))
            self.assertTrue(case.closed)


class CaseRuleOnSaveTests(BaseCaseRuleTest):

    def enable_updates_on_save(self):
        update_toggle_cache(RUN_AUTO_CASE_UPDATES_ON_SAVE.slug, self.domain, True, NAMESPACE_DOMAIN)

    def disable_updates_on_save(self):
        update_toggle_cache(RUN_AUTO_CASE_UPDATES_ON_SAVE.slug, self.domain, False, NAMESPACE_DOMAIN)

    def tearDown(self):
        super(CaseRuleOnSaveTests, self).tearDown()
        self.disable_updates_on_save()

    @run_with_all_backends
    def test_run_on_save(self):
        self.enable_updates_on_save()

        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='do_update',
            property_value='Y',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'do_update': 'N'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertNotIn('result', case.dynamic_case_properties())

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'do_update': 'Y'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertEqual(case.get_case_property('result'), 'abc')

    @run_with_all_backends
    def test_do_not_run_on_save_in_response_to_auto_update(self):
        self.enable_updates_on_save()

        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='do_update',
            property_value='Y',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:

            # When the last update is an auto case update, we don't run the rule on save
            with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.run_rule') as run_rule_patch:
                hqcase.utils.update_case(self.domain, case.case_id, case_properties={'do_update': 'Y'},
                    xmlns=AUTO_UPDATE_XMLNS)
                run_rule_patch.assert_not_called()

    @run_with_all_backends
    def test_do_not_run_on_save_when_flag_is_disabled(self):
        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            with patch('corehq.apps.data_interfaces.tasks.run_case_update_rules_on_save') as task_patch:
                hqcase.utils.update_case(case.domain, case.case_id, case_properties={'property': 'value'})
                task_patch.assert_not_called()


class CaseRuleEndToEndTests(BaseCaseRuleTest):

    @classmethod
    def setUpClass(cls):
        super(CaseRuleEndToEndTests, cls).setUpClass()
        cls.domain_object = Domain(name=cls.domain)
        cls.domain_object.save()

    @classmethod
    def tearDownClass(cls):
        cls.domain_object.delete()
        super(CaseRuleEndToEndTests, cls).tearDownClass()

    def test_get_rules_from_domain(self):
        rule1 = _create_empty_rule(self.domain, case_type='person-1')
        rule2 = _create_empty_rule(self.domain, case_type='person-1')
        rule3 = _create_empty_rule(self.domain, case_type='person-2')
        rule4 = _create_empty_rule(self.domain, case_type='person-2', active=False)
        rule5 = _create_empty_rule(self.domain, case_type='person-3', deleted=True)

        rules = AutomaticUpdateRule.by_domain(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)

        expected_case_types = ['person-1', 'person-2']
        actual_case_types = list(rules_by_case_type)
        self.assertEqual(expected_case_types, sorted(actual_case_types))

        expected_rule_ids = [rule1.pk, rule2.pk]
        actual_rule_ids = [rule.pk for rule in rules_by_case_type['person-1']]
        self.assertEqual(sorted(expected_rule_ids), sorted(actual_rule_ids))

        expected_rule_ids = [rule3.pk]
        actual_rule_ids = [rule.pk for rule in rules_by_case_type['person-2']]
        self.assertEqual(expected_rule_ids, actual_rule_ids)

    def test_boundary_date(self):
        rule1 = _create_empty_rule(self.domain, case_type='person-1')
        rule1.filter_on_server_modified = True
        rule1.server_modified_boundary = 10
        rule1.save()

        rule2 = _create_empty_rule(self.domain, case_type='person-1')
        rule2.filter_on_server_modified = True
        rule2.server_modified_boundary = 20
        rule2.save()

        rule3 = _create_empty_rule(self.domain, case_type='person-2')
        rule3.filter_on_server_modified = True
        rule3.server_modified_boundary = 30
        rule3.save()

        rule4 = _create_empty_rule(self.domain, case_type='person-2')

        rules = AutomaticUpdateRule.by_domain(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)

        boundary_date = AutomaticUpdateRule.get_boundary_date(
            rules_by_case_type['person-1'], datetime(2016, 1, 1))
        self.assertEqual(boundary_date, datetime(2015, 12, 22))

        boundary_date = AutomaticUpdateRule.get_boundary_date(
            rules_by_case_type['person-2'], datetime(2016, 1, 1))
        self.assertIsNone(boundary_date)

    def assertRuleRunCount(self, count):
        self.assertEqual(DomainCaseRuleRun.objects.count(), count)

    def assertLastRuleRun(self, cases_checked, num_updates=0, num_closes=0, num_related_updates=0,
            num_related_closes=0, num_creates=0):
        last_run = DomainCaseRuleRun.objects.filter(domain=self.domain).order_by('-finished_on')[0]
        self.assertEqual(last_run.status, DomainCaseRuleRun.STATUS_FINISHED)
        self.assertEqual(last_run.cases_checked, cases_checked)
        self.assertEqual(last_run.num_updates, num_updates)
        self.assertEqual(last_run.num_closes, num_closes)
        self.assertEqual(last_run.num_related_updates, num_related_updates)
        self.assertEqual(last_run.num_related_closes, num_related_closes)
        self.assertEqual(last_run.num_creates, num_creates)

    @run_with_all_backends
    def test_scheduled_task_run(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='do_update',
            property_value='Y',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.get_case_ids') as case_ids_patch:
                case_ids_patch.return_value = [case.case_id]
                self.assertRuleRunCount(0)

                # Case does not match, nothing to update
                run_case_update_rules_for_domain(self.domain)
                self.assertRuleRunCount(1)
                self.assertLastRuleRun(1)

                # Case matches, perform one update
                hqcase.utils.update_case(self.domain, case.case_id, case_properties={'do_update': 'Y'})
                case = CaseAccessors(self.domain).get_case(case.case_id)
                self.assertNotIn('result', case.dynamic_case_properties())

                run_case_update_rules_for_domain(self.domain)
                self.assertRuleRunCount(2)
                self.assertLastRuleRun(1, num_updates=1)
                case = CaseAccessors(self.domain).get_case(case.case_id)
                self.assertEqual(case.get_case_property('result'), 'abc')

                # Case matches but is already in the desired state, no update made
                run_case_update_rules_for_domain(self.domain)
                self.assertRuleRunCount(3)
                self.assertLastRuleRun(1)
