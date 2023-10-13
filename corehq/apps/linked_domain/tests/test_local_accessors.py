from django.test import SimpleTestCase
from unittest.mock import MagicMock, patch
from datetime import date
from corehq.apps.data_interfaces.models import AutomaticUpdateRule

from corehq.apps.linked_domain.local_accessors import rule_to_dict


class RuleToDictTests(SimpleTestCase):
    def test_removes_extraneous_fields(self):
        rule = AutomaticUpdateRule(
            name='test_rule',
            domain='test_domain',
            case_type='test_case',
            active=True,
            deleted=False,
            last_run=date(2020, 2, 20),
            filter_on_server_modified=True,
            server_modified_boundary=5,
            workflow='test_workflow',
            locked_for_editing=False,
            upstream_id='upstream_id',
            id=15
        )

        result = rule_to_dict(rule)
        self.assertNotIn('last_run', result['rule'])
        self.assertNotIn('locked_for_editing', result['rule'])

    def setUp(self):
        empty_criteria_set = MagicMock()
        empty_criteria_set.all = lambda: []
        criteria_patcher = patch.object(AutomaticUpdateRule, 'caserulecriteria_set', empty_criteria_set)
        criteria_patcher.start()
        self.addCleanup(criteria_patcher.stop)

        empty_case_action_set = MagicMock()
        empty_case_action_set.all = lambda: []
        action_patcher = patch.object(AutomaticUpdateRule, 'caseruleaction_set', empty_case_action_set)
        action_patcher.start()
        self.addCleanup(action_patcher.stop)
