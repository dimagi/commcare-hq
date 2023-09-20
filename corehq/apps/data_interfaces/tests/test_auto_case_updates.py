from contextlib import contextmanager
from datetime import datetime
from unittest.mock import patch

from django.test import TestCase, override_settings

from casexml.apps.case.mock import CaseFactory

from corehq.apps import hqcase
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    CaseRuleActionResult,
    CaseRuleSubmission,
    CaseRuleUndoer,
    ClosedParentDefinition,
    CreateScheduleInstanceActionDefinition,
    CustomActionDefinition,
    CustomMatchDefinition,
    DomainCaseRuleRun,
    LocationFilterDefinition,
    MatchPropertyDefinition,
    UCRFilterDefinition,
    UpdateCaseDefinition,
)
from corehq.apps.data_interfaces.tasks import run_case_update_rules_for_domain
from corehq.apps.domain.models import Domain
from corehq.form_processor.models import CommCareCase, XFormInstance
from corehq.form_processor.signals import sql_case_post_save
from corehq.tests.locks import reentrant_redis_locks
from corehq.toggles import NAMESPACE_DOMAIN, RUN_AUTO_CASE_UPDATES_ON_SAVE
from corehq.util.context_managers import drop_connected_signals
from corehq.util.test_utils import set_parent_case as set_actual_parent_case


@contextmanager
def _with_case(domain, case_type, last_modified, **kwargs):
    with drop_connected_signals(sql_case_post_save):
        case = CaseFactory(domain).create_case(case_type=case_type, **kwargs)

    _update_case(domain, case.case_id, last_modified)
    case = CommCareCase.objects.get_case(case.case_id, domain)
    try:
        yield case
    finally:
        CommCareCase.objects.hard_delete_cases(domain, [case.case_id])


def _save_case(domain, case):
    case.save(with_tracked_models=True)


def _update_case(domain, case_id, server_modified_on, last_visit_date=None, owner_id=None):
    case = CommCareCase.objects.get_case(case_id, domain)
    case.server_modified_on = server_modified_on
    if last_visit_date:
        set_case_property_directly(case, 'last_visit_date', last_visit_date.strftime('%Y-%m-%d'))
    if owner_id:
        case.owner_id = owner_id

    _save_case(domain, case)


def set_parent_case(domain, child_case, parent_case, relationship='child', identifier='parent'):
    server_modified_on = child_case.server_modified_on
    set_actual_parent_case(domain, child_case, parent_case, relationship=relationship, identifier=identifier)

    child_case = CommCareCase.objects.get_case(child_case.case_id, domain)
    child_case.server_modified_on = server_modified_on
    _save_case(domain, child_case)
    return CommCareCase.objects.get_case(child_case.case_id, domain)


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
        workflow=AutomaticUpdateRule.WORKFLOW_CASE_UPDATE,
    )


class BaseCaseRuleTest(TestCase):
    domain = 'case-rule-test'

    def tearDown(self):
        for rule in AutomaticUpdateRule.objects.filter(domain=self.domain):
            rule.hard_delete()

        DomainCaseRuleRun.objects.filter(domain=self.domain).delete()


class CaseRuleCriteriaTest(BaseCaseRuleTest):

    def test_match_case_type(self):
        rule = _create_empty_rule(self.domain)

        with _with_case(self.domain, 'child', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    def test_server_modified(self):
        rule = _create_empty_rule(self.domain)
        rule.filter_on_server_modified = True
        rule.server_modified_boundary = 10
        rule.save()

        with _with_case(self.domain, 'person', datetime(2017, 4, 25)) as case:
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 26)))

        with _with_case(self.domain, 'person', datetime(2017, 4, 15)) as case:
            self.assertTrue(rule.criteria_match(case, datetime(2017, 4, 26)))

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'negative'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': 'negative'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

    def test_case_property_regex_match(self):
        rule1 = _create_empty_rule(self.domain)
        rule1.add_criteria(
            MatchPropertyDefinition,
            property_name='category',
            property_value='^(a|b)$',
            match_type=MatchPropertyDefinition.MATCH_REGEX,
        )

        rule2 = _create_empty_rule(self.domain)
        rule2.add_criteria(
            MatchPropertyDefinition,
            property_name='category',
            property_value='(',
            match_type=MatchPropertyDefinition.MATCH_REGEX,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule1.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'category': 'a'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule1.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'category': 'b'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule1.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'category': 'c'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule1.criteria_match(case, datetime.utcnow()))

            # Running an invalid regex just causes it to return False
            self.assertFalse(rule2.criteria_match(case, datetime.utcnow()))

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule1.criteria_match(case, datetime.utcnow()))
            self.assertFalse(rule2.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'last_visit': '2017-03-02'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule1.criteria_match(case, datetime.utcnow()))
            self.assertTrue(rule2.criteria_match(case, datetime.utcnow()))

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': ''})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'result': ''})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertTrue(rule1.criteria_match(case, datetime(2017, 1, 5)))
            self.assertFalse(rule1.criteria_match(case, datetime(2017, 1, 10)))
            self.assertFalse(rule1.criteria_match(case, datetime(2017, 1, 15)))

            self.assertTrue(rule2.criteria_match(case, datetime(2017, 1, 10)))
            self.assertFalse(rule2.criteria_match(case, datetime(2017, 1, 15)))
            self.assertFalse(rule2.criteria_match(case, datetime(2017, 1, 20)))

            self.assertTrue(rule3.criteria_match(case, datetime(2017, 1, 15)))
            self.assertFalse(rule3.criteria_match(case, datetime(2017, 1, 20)))
            self.assertFalse(rule3.criteria_match(case, datetime(2017, 1, 25)))

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertFalse(rule1.criteria_match(case, datetime(2017, 1, 5)))
            self.assertTrue(rule1.criteria_match(case, datetime(2017, 1, 10)))
            self.assertTrue(rule1.criteria_match(case, datetime(2017, 1, 15)))

            self.assertFalse(rule2.criteria_match(case, datetime(2017, 1, 10)))
            self.assertTrue(rule2.criteria_match(case, datetime(2017, 1, 15)))
            self.assertTrue(rule2.criteria_match(case, datetime(2017, 1, 20)))

            self.assertFalse(rule3.criteria_match(case, datetime(2017, 1, 15)))
            self.assertTrue(rule3.criteria_match(case, datetime(2017, 1, 20)))
            self.assertTrue(rule3.criteria_match(case, datetime(2017, 1, 25)))

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
            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

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
            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

    def test_parent_case_closed(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(ClosedParentDefinition)

        with _with_case(self.domain, 'person', datetime.utcnow()) as child, \
                _with_case(self.domain, 'person', datetime.utcnow()) as parent:

            child = set_parent_case(self.domain, child, parent)
            self.assertFalse(rule.criteria_match(child, datetime.utcnow()))

            hqcase.utils.update_case(self.domain, parent.case_id, close=True)
            # reset memoized cache
            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            self.assertTrue(rule.criteria_match(child, datetime.utcnow()))

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

    def test_multiple_criteria_ALL(self):
        rule = _create_empty_rule(self.domain)

        rule.filter_on_server_modified = True
        rule.server_modified_boundary = 10
        # Default criteria_operator = 'ALL'
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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 10)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 1)
            set_case_property_directly(case, 'abc', '123x')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 1)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456x')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime(2017, 4, 15)))

            case.server_modified_on = datetime(2017, 4, 1)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime(2017, 4, 15)))

    def test_multiple_criteria_ANY(self):
        rule = _create_empty_rule(self.domain)

        rule.filter_on_server_modified = True
        rule.server_modified_boundary = 3
        rule.criteria_operator = 'ANY'
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
            case.server_modified_on = datetime(2022, 4, 1)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime(2022, 4, 15)))

            case.server_modified_on = datetime(2022, 4, 14)
            set_case_property_directly(case, 'abc', '123')
            set_case_property_directly(case, 'def', '456x')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime(2022, 4, 15)))

            case.server_modified_on = datetime(2022, 4, 1)
            set_case_property_directly(case, 'abc', '123x')
            set_case_property_directly(case, 'def', '456x')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime(2022, 4, 15)))

            case.server_modified_on = datetime(2022, 4, 14)
            set_case_property_directly(case, 'abc', '123x')
            set_case_property_directly(case, 'def', '456x')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime(2022, 4, 15)))

            rule.filter_on_server_modified = False
            rule.server_modified_boundary = None
            rule.save()
            set_case_property_directly(case, 'abc', '123x')
            set_case_property_directly(case, 'def', '456x')
            _save_case(self.domain, case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertFalse(rule.criteria_match(case, datetime(2022, 4, 15)))

    def test_location_filter_criteria_does_not_include_child_locations(self):
        location_id = 'diagon_alley_id'
        # Create location and child; assign case to child
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            LocationFilterDefinition,
            location_id=location_id,
            include_child_locations=False,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            _update_case(self.domain, case.case_id, case.server_modified_on, owner_id=location_id)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    def test_location_filter_criteria_does_include_child_locations(self):
        from corehq.apps.domain.shortcuts import create_domain
        from corehq.apps.locations.models import LocationType, SQLLocation

        domain_obj = create_domain(self.domain)
        self.addCleanup(domain_obj.delete)

        location_type_provice = LocationType(domain=self.domain, name='Province')
        location_type_provice.save()

        location_type_city = LocationType(domain=self.domain, name='City', parent_type=location_type_provice)
        location_type_city.save()

        western_cape = SQLLocation.objects.create(
            domain=self.domain,
            name='Western Cape',
            location_type=location_type_provice,
        )

        cape_town = SQLLocation.objects.create(
            domain=self.domain,
            name='Cape Town',
            location_type=location_type_city,
            parent=western_cape,
        )

        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            LocationFilterDefinition,
            location_id=western_cape.location_id,
            include_child_locations=True,
        )

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertFalse(rule.criteria_match(case, datetime.utcnow()))

            _update_case(self.domain, case.case_id, case.server_modified_on, owner_id=cape_town.location_id)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertTrue(rule.criteria_match(case, datetime.utcnow()))

    def test_ucr_filter(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            UCRFilterDefinition,
            configured_filter={
                "type": "boolean_expression",
                "expression": {
                    "type": "property_name",
                    "property_name": "prop",
                },
                "operator": "eq",
                "property_value": "act-on-me",
            }
        )

        with _with_case(self.domain, "person", datetime.utcnow(), update={"prop": "dont-act-on-me"}) as case:
            now = datetime.utcnow()
            self.assertFalse(rule.criteria_match(case, now))

        with _with_case(self.domain, "person", datetime.utcnow(), update={"prop": "act-on-me"}) as case:
            now = datetime.utcnow()
            self.assertTrue(rule.criteria_match(case, now))


def set_case_property_directly(case, property_name, value):
    case.case_json[property_name] = value


class CaseRuleActionsTest(BaseCaseRuleTest):

    def assertActionResult(self, rule, submission_count, result=None, expected_result=None):
        self.assertEqual(CaseRuleSubmission.objects.count(), submission_count)

        for submission in CaseRuleSubmission.objects.all():
            self.assertEqual(submission.domain, self.domain)
            self.assertEqual(submission.rule_id, rule.pk)

        if result and expected_result:
            self.assertEqual(result, expected_result)

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertIn('result1', case.case_json)
            self.assertIn('result2', case.case_json)
            self.assertEqual(case.get_case_property('result1'), 'abc')
            self.assertEqual(case.get_case_property('result2'), 'def')
            self.assertFalse(case.closed)

    def test_update_case_name(self):
        """
        Updating case property "case_name" updates ``case.name``
        """
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='case_name',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='Ellie',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertEqual(case.name, '')
            self.assertActionResult(rule, 0)

            result = rule.run_actions_when_case_matches(case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertNotIn('case_name', case.case_json)
            self.assertEqual(case.name, 'Ellie')

    def test_update_name(self):
        """
        Updating case property "name" updates ``case.name``
        """
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='name',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='Ellie',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertEqual(case.name, '')
            self.assertActionResult(rule, 0)

            result = rule.run_actions_when_case_matches(case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertNotIn('name', case.case_json)
            self.assertEqual(case.name, 'Ellie')

    def test_update_external_id(self):
        """
        Updating case property "external_id" updates ``case.external_id``
        """
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='external_id',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='Bella Ramsay',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertActionResult(rule, 0)

            result = rule.run_actions_when_case_matches(case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertNotIn('external_id', case.case_json)
            self.assertEqual(case.external_id, 'Bella Ramsay')

    def test_update_case_id(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='case_id',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='Bella Ramsay',
            ),
        ])
        definition.save()

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            orig_case_id = case.case_id
            self.assertActionResult(rule, 0)

            result = rule.run_actions_when_case_matches(case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))

            self.assertNotIn('case_id', case.case_json)
            self.assertEqual(case.case_id, orig_case_id)

    def test_close_only(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=True)

        with _with_case(self.domain, 'person', datetime.utcnow()) as case:
            self.assertActionResult(rule, 0)

            dynamic_properties_before = case.dynamic_case_properties()
            result = rule.run_actions_when_case_matches(case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            dynamic_properties_after = case.dynamic_case_properties()

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_closes=1))
            self.assertTrue(case.closed)
            self.assertEqual(dynamic_properties_before, dynamic_properties_after)

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
            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            parent = CommCareCase.objects.get_case(parent.case_id, self.domain)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_related_updates=1))
            self.assertEqual(parent.get_case_property('result'), 'abc')
            self.assertEqual(child.dynamic_case_properties(), child_dynamic_properties_before)

            self.assertFalse(child.closed)
            self.assertFalse(parent.closed)

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
            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            host = CommCareCase.objects.get_case(host.case_id, self.domain)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_related_updates=1))
            self.assertEqual(host.get_case_property('result'), 'abc')
            self.assertEqual(child.dynamic_case_properties(), child_dynamic_properties_before)

            self.assertFalse(child.closed)
            self.assertFalse(host.closed)

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertNotIn('result', case.dynamic_case_properties())

            result = rule.run_actions_when_case_matches(case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertEqual(case.get_case_property('result'), 'xyz')
            self.assertEqual(case.get_case_property('other_result'), 'xyz')
            self.assertFalse(case.closed)

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
            parent = CommCareCase.objects.get_case(parent.case_id, self.domain)
            self.assertNotIn('result', child.dynamic_case_properties())
            parent_case_properties_before = parent.dynamic_case_properties()

            result = rule.run_actions_when_case_matches(child)
            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            parent = CommCareCase.objects.get_case(parent.case_id, self.domain)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_updates=1))
            self.assertEqual(child.get_case_property('result'), 'xyz')
            self.assertEqual(parent.dynamic_case_properties(), parent_case_properties_before)
            self.assertFalse(child.closed)
            self.assertFalse(parent.closed)

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            server_modified_before = case.server_modified_on
            self.assertEqual(case.get_case_property('result'), 'xyz')

            result = rule.run_actions_when_case_matches(case)
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertEqual(case.server_modified_on, server_modified_before)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 0, result, CaseRuleActionResult())
            self.assertFalse(case.closed)

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

            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            parent = CommCareCase.objects.get_case(parent.case_id, self.domain)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 2, result,
                CaseRuleActionResult(num_updates=1, num_closes=1, num_related_updates=1))

            self.assertEqual(child.get_case_property('result'), 'abc')
            self.assertEqual(parent.get_case_property('result'), 'def')

            self.assertTrue(child.closed)
            self.assertFalse(parent.closed)

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

            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            parent = CommCareCase.objects.get_case(parent.case_id, self.domain)

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

            child = CommCareCase.objects.get_case(child.case_id, self.domain)
            parent = CommCareCase.objects.get_case(parent.case_id, self.domain)

            self.assertNotIn('result', child.dynamic_case_properties())
            self.assertNotIn('result', parent.dynamic_case_properties())

            self.assertFalse(child.closed)
            self.assertFalse(parent.closed)

            self.assertEqual(CaseRuleSubmission.objects.filter(domain=self.domain).count(), 2)
            self.assertEqual(CaseRuleSubmission.objects.filter(domain=self.domain, archived=True).count(), 2)

            form_ids = CaseRuleSubmission.objects.filter(domain=self.domain).values_list('form_id', flat=True)
            for form in XFormInstance.objects.iter_forms(form_ids, self.domain):
                self.assertTrue(form.is_archived)

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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)

            self.assertTrue(isinstance(result, CaseRuleActionResult))
            self.assertActionResult(rule, 1, result, CaseRuleActionResult(num_closes=1, num_related_updates=1))
            self.assertTrue(case.closed)


class CaseRuleOnSaveTests(BaseCaseRuleTest):

    def enable_updates_on_save(self):
        RUN_AUTO_CASE_UPDATES_ON_SAVE.set(self.domain, True, NAMESPACE_DOMAIN)

    def disable_updates_on_save(self):
        RUN_AUTO_CASE_UPDATES_ON_SAVE.set(self.domain, False, NAMESPACE_DOMAIN)

    def tearDown(self):
        super(CaseRuleOnSaveTests, self).tearDown()
        self.disable_updates_on_save()

    @reentrant_redis_locks()
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
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertNotIn('result', case.dynamic_case_properties())

            hqcase.utils.update_case(self.domain, case.case_id, case_properties={'do_update': 'Y'})
            case = CommCareCase.objects.get_case(case.case_id, self.domain)
            self.assertEqual(case.get_case_property('result'), 'abc')

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
                    xmlns=hqcase.utils.AUTO_UPDATE_XMLNS)
                run_rule_patch.assert_not_called()

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
        cls.addClassCleanup(cls.domain_object.delete)

    def test_get_rules_from_domain(self):
        rule1 = _create_empty_rule(self.domain, case_type='person-1')
        rule2 = _create_empty_rule(self.domain, case_type='person-1')
        rule3 = _create_empty_rule(self.domain, case_type='person-2')
        _create_empty_rule(self.domain, case_type='person-2', active=False)
        _create_empty_rule(self.domain, case_type='person-3', deleted=True)

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

        _create_empty_rule(self.domain, case_type='person-2')

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
            num_related_closes=0, num_creates=0, num_errors=0):
        last_run = DomainCaseRuleRun.objects.filter(domain=self.domain).order_by('-finished_on')[0]
        expected_status = DomainCaseRuleRun.STATUS_HAD_ERRORS if num_errors else DomainCaseRuleRun.STATUS_FINISHED
        self.assertEqual(last_run.status, expected_status)
        self.assertEqual(last_run.cases_checked, cases_checked)
        self.assertEqual(last_run.num_updates, num_updates)
        self.assertEqual(last_run.num_closes, num_closes)
        self.assertEqual(last_run.num_related_updates, num_related_updates)
        self.assertEqual(last_run.num_related_closes, num_related_closes)
        self.assertEqual(last_run.num_creates, num_creates)
        self.assertEqual(last_run.num_errors, num_errors)

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
            with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.iter_cases') as iter_cases_patch:
                iter_cases_patch.return_value = [case]
                self.assertRuleRunCount(0)

                # Case does not match, nothing to update
                run_case_update_rules_for_domain(self.domain)
                self.assertRuleRunCount(1)
                self.assertLastRuleRun(1)

                # Case matches, perform one update
                hqcase.utils.update_case(self.domain, case.case_id, case_properties={'do_update': 'Y'})
                case = CommCareCase.objects.get_case(case.case_id, self.domain)
                self.assertNotIn('result', case.dynamic_case_properties())

                iter_cases_patch.return_value = [case]
                run_case_update_rules_for_domain(self.domain)
                self.assertRuleRunCount(2)
                self.assertLastRuleRun(1, num_updates=1)
                case = CommCareCase.objects.get_case(case.case_id, self.domain)
                self.assertEqual(case.get_case_property('result'), 'abc')

                # Case matches but is already in the desired state, no update made
                iter_cases_patch.return_value = [case]
                run_case_update_rules_for_domain(self.domain)
                self.assertRuleRunCount(3)
                self.assertLastRuleRun(1)

    def test_single_failure_is_isolated(self):

        def fail_on_person2(case, now):
            if case.type == 'person2':
                raise AssertionError()
            return CaseRuleActionResult(num_updates=1)

        _create_empty_rule(self.domain)
        with _with_case(self.domain, 'person1', datetime.utcnow()) as case1, \
                _with_case(self.domain, 'person2', datetime.utcnow()) as case2, \
                _with_case(self.domain, 'person3', datetime.utcnow()) as case3, \
                patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.iter_cases') as iter_cases_patch, \
                patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.run_rule') as run_rule:
            iter_cases_patch.return_value = [case1, case2, case3]
            run_rule.side_effect = fail_on_person2

            self.assertRuleRunCount(0)
            run_case_update_rules_for_domain(self.domain)
            self.assertRuleRunCount(1)
            # Three cases were checked, two were updated, one failed hard
            self.assertLastRuleRun(cases_checked=3, num_updates=2, num_errors=1)


class TestParentCaseReferences(BaseCaseRuleTest):

    def test_closed_parent_criteria(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(ClosedParentDefinition)
        self.assertTrue(rule.references_parent_case)

    def test_match_property_criteria(self):
        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='status',
            property_value='green',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        self.assertFalse(rule.references_parent_case)

        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='parent/status',
            property_value='green',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        self.assertTrue(rule.references_parent_case)

        rule = _create_empty_rule(self.domain)
        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='host/status',
            property_value='green',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )
        self.assertTrue(rule.references_parent_case)

    def test_update_case_action(self):
        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_EXACT,
                value='abc',
            ),
        ])
        definition.save()
        self.assertFalse(rule.references_parent_case)

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
        self.assertTrue(rule.references_parent_case)

        rule = _create_empty_rule(self.domain)
        _, definition = rule.add_action(UpdateCaseDefinition, close_case=False)
        definition.set_properties_to_update([
            UpdateCaseDefinition.PropertyDefinition(
                name='result',
                value_type=UpdateCaseDefinition.VALUE_TYPE_CASE_PROPERTY,
                value='parent/abc',
            ),
        ])
        definition.save()
        self.assertTrue(rule.references_parent_case)

    def test_create_schedule_instance_action(self):
        rule = _create_empty_rule(self.domain)
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            reset_case_property_name='abc',
            start_date_case_property='def',
        )
        self.assertFalse(rule.references_parent_case)

        rule = _create_empty_rule(self.domain)
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            reset_case_property_name='parent/abc',
        )
        self.assertTrue(rule.references_parent_case)

        rule = _create_empty_rule(self.domain)
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            start_date_case_property='parent/abc',
        )
        self.assertTrue(rule.references_parent_case)
