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

        case = CommCareCase(domain=self.domain, type='test-case-type')
        case.save()
        self.case_id = case.get_id

    def tearDown(self):
        AutomaticUpdateRuleCriteria.objects.filter(rule_id=self.rule.pk).delete()
        AutomaticUpdateAction.objects.filter(rule_id=self.rule.pk).delete()
        self.rule.delete()
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
