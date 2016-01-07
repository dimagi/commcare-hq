from casexml.apps.case.models import CommCareCase
from corehq.apps.data_interfaces.models import (AutomaticUpdateRule,
    AutomaticUpdateRuleCriteria, AutomaticUpdateAction)
from corehq.apps.data_interfaces.tasks import run_case_update_rules_for_domain
from datetime import datetime, date
from dimagi.utils.parsing import json_format_datetime
from django.test import TestCase
from mock import patch


class AutomaticCaseUpdateTest(TestCase):
    def setUp(self):
        self.now = datetime(2015, 10, 22, 0, 0)
        self.domain = 'auto-update-test'
        self.rule = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule',
            case_type='test-case-type',
            active=True,
            server_modified_boundary=30,
        )
        self.rule.save()
        self.rule.automaticupdaterulecriteria_set = [
            AutomaticUpdateRuleCriteria(
                property_name='last_visit_date',
                property_value='30',
                match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_SINCE,
            ),
        ]
        self.rule.automaticupdateaction_set = [
            AutomaticUpdateAction(
                action=AutomaticUpdateAction.ACTION_UPDATE,
                property_name='update_flag',
                property_value='Y',
            ),
            AutomaticUpdateAction(
                action=AutomaticUpdateAction.ACTION_CLOSE,
            ),
        ]

        self.rule2 = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule-2',
            case_type='test-case-type-2',
            active=True,
            server_modified_boundary=30,
        )
        self.rule2.save()
        self.rule2.automaticupdateaction_set = [
            AutomaticUpdateAction(
                action=AutomaticUpdateAction.ACTION_CLOSE,
            ),
        ]

        self.rule3 = AutomaticUpdateRule(
            domain=self.domain,
            name='test-rule-3',
            case_type='test-case-type-2',
            active=True,
            server_modified_boundary=50,
        )
        self.rule3.save()
        self.rule3.automaticupdateaction_set = [
            AutomaticUpdateAction(
                action=AutomaticUpdateAction.ACTION_CLOSE,
            ),
        ]

        case = CommCareCase(domain=self.domain, type='test-case-type')
        case.save()
        self.case_id = case.get_id

    def tearDown(self):
        AutomaticUpdateRuleCriteria.objects.all().delete()
        AutomaticUpdateAction.objects.all().delete()
        AutomaticUpdateRule.objects.all().delete()
        CommCareCase.get(self.case_id).delete()

    def _get_case_ids(self, *args, **kwargs):
        return [self.case_id]

    def _get_case(self):
        return CommCareCase.get_db().get(self.case_id)

    def _update_case(self, server_modified_on, last_visit_date):
        doc = self._get_case()
        doc['server_modified_on'] = json_format_datetime(server_modified_on)
        doc['last_visit_date'] = last_visit_date.strftime('%Y-%m-%d')
        CommCareCase.get_db().save_doc(doc)

    def _assert_case_revision(self, number):
        doc = CommCareCase.get_db().get(self.case_id)
        self.assertTrue(doc['_rev'].startswith('%s-' % number))

    def test_rule(self):
        self._assert_case_revision(1)
        with patch('corehq.apps.data_interfaces.models.AutomaticUpdateRule.get_case_ids', new=self._get_case_ids):
            # No update: both dates are 27 days away
            self._update_case(datetime(2015, 9, 25, 12, 0), date(2015, 9, 25))
            self._assert_case_revision(2)
            run_case_update_rules_for_domain(self.domain, now=self.now)
            self._assert_case_revision(2)

            # No update: server_modified_on is 32 days away but last_visit_date is 27 days away
            self._update_case(datetime(2015, 9, 20, 12, 0), date(2015, 9, 25))
            self._assert_case_revision(3)
            run_case_update_rules_for_domain(self.domain, now=self.now)
            self._assert_case_revision(3)

            # No update: last_visit_date is 32 days away but server_modified_on is 27 days away
            self._update_case(datetime(2015, 9, 25, 12, 0), date(2015, 9, 20))
            self._assert_case_revision(4)
            run_case_update_rules_for_domain(self.domain, now=self.now)
            self._assert_case_revision(4)

            # Perform update: both dates are 32 days away
            self._update_case(datetime(2015, 9, 20, 12, 0), date(2015, 9, 20))
            self._assert_case_revision(5)
            run_case_update_rules_for_domain(self.domain, now=self.now)
            self._assert_case_revision(6)

            doc = self._get_case()
            self.assertEqual(doc['update_flag'], 'Y')
            self.assertEqual(doc['closed'], True)

    def test_match_days_since(self):
        case = CommCareCase(
            domain=self.domain,
            type='test-case-type-2',
            server_modified_on=datetime(2015, 1, 1),
        )

        self.rule2.automaticupdaterulecriteria_set = [
            AutomaticUpdateRuleCriteria(
                property_name='last_visit_date',
                property_value='30',
                match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_SINCE,
            ),
        ]
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('last_visit_date', '2015-12-30')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('last_visit_date', '2015-12-03')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('last_visit_date', '2015-12-02')
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('last_visit_date', '2015-11-01')
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

    def test_match_equal(self):
        case = CommCareCase(
            domain=self.domain,
            type='test-case-type-2',
            server_modified_on=datetime(2015, 1, 1),
        )

        self.rule2.automaticupdaterulecriteria_set = [
            AutomaticUpdateRuleCriteria(
                property_name='property1',
                property_value='value1',
                match_type=AutomaticUpdateRuleCriteria.MATCH_EQUAL,
            ),
        ]
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property1', 'x')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property1', 'value1')
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

    def test_match_not_equal(self):
        case = CommCareCase(
            domain=self.domain,
            type='test-case-type-2',
            server_modified_on=datetime(2015, 1, 1),
        )

        self.rule2.automaticupdaterulecriteria_set = [
            AutomaticUpdateRuleCriteria(
                property_name='property2',
                property_value='value2',
                match_type=AutomaticUpdateRuleCriteria.MATCH_NOT_EQUAL,
            ),
        ]
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property2', 'value2')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property2', 'x')
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

    def test_match_has_value(self):
        case = CommCareCase(
            domain=self.domain,
            type='test-case-type-2',
            server_modified_on=datetime(2015, 1, 1),
        )

        self.rule2.automaticupdaterulecriteria_set = [
            AutomaticUpdateRuleCriteria(
                property_name='property3',
                match_type=AutomaticUpdateRuleCriteria.MATCH_HAS_VALUE,
            ),
        ]
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property3', 'x')
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property3', '')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

    def test_and_criteria(self):
        case = CommCareCase(
            domain=self.domain,
            type='test-case-type-2',
            server_modified_on=datetime(2015, 1, 1),
        )

        self.rule2.automaticupdaterulecriteria_set = [
            AutomaticUpdateRuleCriteria(
                property_name='last_visit_date',
                property_value='30',
                match_type=AutomaticUpdateRuleCriteria.MATCH_DAYS_SINCE,
            ),
            AutomaticUpdateRuleCriteria(
                property_name='property1',
                property_value='value1',
                match_type=AutomaticUpdateRuleCriteria.MATCH_EQUAL,
            ),
            AutomaticUpdateRuleCriteria(
                property_name='property2',
                property_value='value2',
                match_type=AutomaticUpdateRuleCriteria.MATCH_NOT_EQUAL,
            ),
            AutomaticUpdateRuleCriteria(
                property_name='property3',
                match_type=AutomaticUpdateRuleCriteria.MATCH_HAS_VALUE,
            ),
        ]

        case.set_case_property('last_visit_date', '2015-11-01')
        case.set_case_property('property1', 'value1')
        case.set_case_property('property2', 'x')
        case.set_case_property('property3', 'x')
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('last_visit_date', '2015-12-30')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('last_visit_date', '2015-11-01')
        case.set_case_property('property1', 'x')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property1', 'value1')
        case.set_case_property('property2', 'value2')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property2', 'x')
        case.set_case_property('property3', '')
        self.assertFalse(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

        case.set_case_property('property3', 'x')
        self.assertTrue(self.rule2.rule_matches_case(case, datetime(2016, 1, 1)))

    def test_get_rules_from_domain(self):
        rules = AutomaticUpdateRule.by_domain(self.domain)
        rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)

        expected_case_types = ['test-case-type', 'test-case-type-2']
        actual_case_types = rules_by_case_type.keys()
        self.assertEqual(set(expected_case_types), set(actual_case_types))

        expected_rule_ids = [self.rule.pk]
        actual_rule_ids = [rule.pk for rule in rules_by_case_type['test-case-type']]
        self.assertEqual(set(expected_rule_ids), set(actual_rule_ids))

        expected_rule_ids = [self.rule2.pk, self.rule3.pk]
        actual_rule_ids = [rule.pk for rule in rules_by_case_type['test-case-type-2']]
        self.assertEqual(set(expected_rule_ids), set(actual_rule_ids))

    def test_boundary_date(self):
        rules = AutomaticUpdateRule.by_domain(self.domain)
        rules_by_case_type = AutomaticUpdateRule.organize_rules_by_case_type(rules)

        boundary_date = AutomaticUpdateRule.get_boundary_date(rules_by_case_type['test-case-type'], datetime(2016, 1, 1))
        self.assertEqual(boundary_date, datetime(2015, 12, 2))

        boundary_date = AutomaticUpdateRule.get_boundary_date(rules_by_case_type['test-case-type-2'], datetime(2016, 1, 1))
        self.assertEqual(boundary_date, datetime(2015, 12, 2))
