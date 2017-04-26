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
    CaseRuleCriteria,
    CaseRuleAction,
    CaseRuleSubmission,
)
from corehq.apps.data_interfaces.tasks import run_case_update_rules_for_domain
from datetime import datetime, date

from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
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
            filter_on_server_modified=False
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
        CaseRuleSubmission.objects.all().delete()
        AutomaticUpdateRuleCriteria.objects.all().delete()
        AutomaticUpdateAction.objects.all().delete()
        CaseRuleCriteria.objects.all().delete()
        MatchPropertyDefinition.objects.all().delete()
        CaseRuleAction.objects.all().delete()
        UpdateCaseDefinition.objects.all().delete()
        AutomaticUpdateRule.objects.all().delete()
        FormProcessorTestUtils.delete_all_cases(self.domain)
        super(AutomaticCaseUpdateTest, self).tearDown()

    def _get_case_ids(self, *args, **kwargs):
        return [[self.case_id]]

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
        with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.get_case_ids', new=self._get_case_ids):
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
                property_value='30',
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
        rules = AutomaticUpdateRule.by_domain(self.domain)
        rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)

        expected_case_types = ['test-case-type', 'test-case-type-2', 'test-case-type-3']
        actual_case_types = rules_by_case_type.keys()
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
        rules = AutomaticUpdateRule.by_domain(self.domain)
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


def set_parent_case(domain, child_case, parent_case):
    server_modified_on = child_case.server_modified_on
    set_actual_parent_case(domain, child_case, parent_case)

    child_case = CaseAccessors(domain).get_case(child_case.case_id)
    child_case.server_modified_on = server_modified_on
    _save_case(domain, child_case)
    return CaseAccessors(domain).get_case(child_case.case_id)


def dummy_custom_match_function(case, now):
    pass


class CaseRuleCriteriaTest(TestCase):
    domain = 'case-rule-criteria-test'

    @classmethod
    def _create_empty_rule(cls):
        return AutomaticUpdateRule.objects.create(
            domain=cls.domain,
            name='test',
            case_type='person',
            active=True,
            deleted=False,
            filter_on_server_modified=False,
            server_modified_boundary=None,
            migrated=True,
        )

    @run_with_all_backends
    def test_match_case_type(self):
        rule = self._create_empty_rule()
        self.addCleanup(rule.hard_delete)

        with _with_case(self.domain, 'child', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_server_modified(self):
        rule = self._create_empty_rule()
        rule.filter_on_server_modified = True
        rule.server_modified_boundary = 10
        rule.save()
        self.addCleanup(rule.hard_delete)

        with _with_case(self.domain, 'person', datetime(2017, 4, 25)) as case:
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 26)))

        with _with_case(self.domain, 'person', datetime(2017, 4, 15)) as case:
            self.assertTrue(rule.criteria_match(case, datetime(2017, 4, 26)))

    @run_with_all_backends
    def test_case_property_equal(self):
        rule = self._create_empty_rule()
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='result',
            property_value='negative',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        self.addCleanup(rule.hard_delete)

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'x'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'negative'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_case_property_equal(self):
        rule = self._create_empty_rule()
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='result',
            property_value='negative',
            match_type=MatchPropertyDefinition.MATCH_NOT_EQUAL,
        )
        self.addCleanup(rule.hard_delete)

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'x'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'negative'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_case_property_has_value(self):
        rule = self._create_empty_rule()
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='result',
            match_type=MatchPropertyDefinition.MATCH_HAS_VALUE
        )
        self.addCleanup(rule.hard_delete)

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'x'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    @run_with_all_backends
    def test_date_case_property_before(self):
        rule1 = self._create_empty_rule()
        rule1.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
        )
        self.addCleanup(rule1.hard_delete)

        rule2 = self._create_empty_rule()
        rule2.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='0',
            match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
        )
        self.addCleanup(rule2.hard_delete)

        rule3 = self._create_empty_rule()
        rule3.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='-5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_BEFORE,
        )
        self.addCleanup(rule3.hard_delete)

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
        rule1 = self._create_empty_rule()
        rule1.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='-5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
        )
        self.addCleanup(rule1.hard_delete)

        rule2 = self._create_empty_rule()
        rule2.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='0',
            match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
        )
        self.addCleanup(rule2.hard_delete)

        rule3 = self._create_empty_rule()
        rule3.add_criteria(
            MatchPropertyDefinition,
            property_name='last_visit_date',
            property_value='5',
            match_type=MatchPropertyDefinition.MATCH_DAYS_AFTER,
        )
        self.addCleanup(rule3.hard_delete)

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
        rule = self._create_empty_rule()
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='parent/result',
            property_value='negative',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        self.addCleanup(rule.hard_delete)

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
    def test_parent_case_closed(self):
        rule = self._create_empty_rule()
        rule.add_criteria(ClosedParentDefinition)
        self.addCleanup(rule.hard_delete)

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
        rule = self._create_empty_rule()
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
        rule = self._create_empty_rule()

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
        self.addCleanup(rule.hard_delete)

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
