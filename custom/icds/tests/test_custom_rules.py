import pytz
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    DomainCaseRuleRun,
    CustomMatchDefinition,
    CustomActionDefinition,
)
from corehq.apps.data_interfaces.tests.test_auto_case_updates import BaseCaseRuleTest
from corehq.apps.data_interfaces.tests.util import create_case, create_empty_rule
from corehq.apps.hqcase.utils import update_case
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import use_sql_backend
from corehq.util.timezones.conversions import ServerTime
from custom.icds.tests.base import BaseICDSTest
from datetime import datetime


@use_sql_backend
class AutoEscalationTest(BaseCaseRuleTest):
    domain = 'icds-auto-escalation-test'

    @property
    def todays_date(self):
        date = ServerTime(datetime.utcnow()).user_time(pytz.timezone('Asia/Kolkata')).done().date()
        return date.strftime('%Y-%m-%d')

    def _test_auto_escalation(self, from_level, to_level):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rule.add_action(CustomActionDefinition, name='ICDS_ESCALATE_TECH_ISSUE')

        with create_case(
            self.domain,
            'tech_issue',
            case_name='New Issue',
            update={
                'ticket_level': from_level,
                'touch_case_date': '2017-06-01',
                'block_location_id': 'block_id',
                'district_location_id': 'district_id',
                'state_location_id': 'state_id',
            },
        ) as tech_issue:
            properties = tech_issue.to_json()
            self.assertEqual(properties.get('ticket_level'), from_level)
            self.assertEqual(properties.get('touch_case_date'), '2017-06-01')
            self.assertIsNone(properties.get('change_in_level'))

            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 1)
            self.assertEqual(result.num_creates, 1)

            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)
            properties = tech_issue.to_json()
            self.assertEqual(properties.get('ticket_level'), to_level)
            self.assertEqual(properties.get('touch_case_date'), self.todays_date)
            self.assertEqual(properties.get('change_in_level'), '1')

            subcases = tech_issue.get_subcases(index_identifier='parent')
            self.assertEqual(len(subcases), 1)
            [tech_issue_delegate] = subcases

            self.assertEqual(tech_issue_delegate.type, 'tech_issue_delegate')
            self.assertEqual(tech_issue_delegate.name, tech_issue.name)
            self.assertEqual(tech_issue_delegate.owner_id,
                tech_issue.get_case_property('%s_location_id' % to_level))
            self.assertEqual(tech_issue_delegate.get_case_property('change_in_level'), '1')

    def test_auto_escalation_to_block(self):
        self._test_auto_escalation('supervisor', 'block')

    def test_auto_escalation_to_district(self):
        self._test_auto_escalation('block', 'district')

    def test_auto_escalation_to_state(self):
        self._test_auto_escalation('district', 'state')

    def test_no_further_escalation(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rule.add_action(CustomActionDefinition, name='ICDS_ESCALATE_TECH_ISSUE')

        with create_case(
            self.domain,
            'tech_issue',
            case_name='New Issue',
            update={'ticket_level': 'state'},
        ) as tech_issue:
            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 0)
            self.assertEqual(result.num_creates, 0)

    def test_when_delegate_exists(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_CASE_UPDATE)
        rule.add_action(CustomActionDefinition, name='ICDS_ESCALATE_TECH_ISSUE')

        with create_case(
            self.domain,
            'tech_issue',
            case_name='New Issue',
            update={
                'ticket_level': 'block',
                'touch_case_date': '2017-06-01',
                'block_location_id': 'block_id',
                'district_location_id': 'district_id',
                'state_location_id': 'state_id',
            },
        ) as tech_issue:
            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 1)
            self.assertEqual(result.num_creates, 1)
            self.assertEqual(result.num_related_updates, 0)

            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)
            subcases = tech_issue.get_subcases(index_identifier='parent')
            self.assertEqual(len(subcases), 1)
            [tech_issue_delegate] = subcases
            self.assertEqual(tech_issue_delegate.get_case_property('change_in_level'), '1')

            update_case(self.domain, tech_issue.case_id, case_properties={'ticket_level': 'block'})
            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)

            result = rule.run_actions_when_case_matches(tech_issue)
            self.assertEqual(result.num_updates, 1)
            self.assertEqual(result.num_creates, 0)
            self.assertEqual(result.num_related_updates, 1)

            tech_issue = CaseAccessors(self.domain).get_case(tech_issue.case_id)
            subcases = tech_issue.get_subcases(index_identifier='parent')
            self.assertEqual(len(subcases), 1)
            [tech_issue_delegate] = subcases
            self.assertEqual(tech_issue_delegate.get_case_property('change_in_level'), '2')


class BaseMigratedCriteriaTestCase(BaseICDSTest):
    domain = 'icds-migrated-cases-test'

    __test__ = False

    @classmethod
    def person_case_update(cls):
        raise NotImplementedError()

    @classmethod
    def should_exclude(cls):
        raise NotImplementedError()

    @classmethod
    def setUpClass(cls):
        super(BaseMigratedCriteriaTestCase, cls).setUpClass()
        cls.create_basic_related_cases()

        if cls.person_case_update():
            update_case(cls.domain, cls.mother_person_case.case_id, case_properties=cls.person_case_update())
            update_case(cls.domain, cls.child_person_case.case_id, case_properties=cls.person_case_update())

            cls.mother_person_case = CaseAccessors(cls.domain).get_case(cls.mother_person_case.case_id)
            cls.child_person_case = CaseAccessors(cls.domain).get_case(cls.child_person_case.case_id)

    def assertExcludedOrNot(self, result):
        if self.should_exclude():
            self.assertFalse(result)
        else:
            self.assertTrue(result)

    def tearDown(self):
        for rule in AutomaticUpdateRule.objects.filter(domain=self.domain):
            rule.hard_delete()

        DomainCaseRuleRun.objects.filter(domain=self.domain).delete()

    def test_person_case(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING, case_type='person')
        rule.add_criteria(
            CustomMatchDefinition,
            name='ICDS_PERSON_CASE_IS_NOT_MIGRATED',
        )
        self.assertExcludedOrNot(rule.criteria_match(self.mother_person_case, datetime.utcnow()))
        self.assertExcludedOrNot(rule.criteria_match(self.child_person_case, datetime.utcnow()))

    def test_child_health_case(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING, case_type='child_health')
        rule.add_criteria(
            CustomMatchDefinition,
            name='ICDS_CHILD_HEALTH_CASE_IS_NOT_MIGRATED',
        )
        self.assertExcludedOrNot(rule.criteria_match(self.child_health_case, datetime.utcnow()))

    def test_ccs_record_case(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING, case_type='ccs_record')
        rule.add_criteria(
            CustomMatchDefinition,
            name='ICDS_CCS_RECORD_CASE_IS_NOT_MIGRATED',
        )
        self.assertExcludedOrNot(rule.criteria_match(self.ccs_record_case, datetime.utcnow()))

    def test_tasks_case(self):
        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING, case_type='tasks')
        rule.add_criteria(
            CustomMatchDefinition,
            name='ICDS_TASKS_CASE_IS_NOT_MIGRATED',
        )
        self.assertExcludedOrNot(rule.criteria_match(self.child_tasks_case, datetime.utcnow()))
        self.assertExcludedOrNot(rule.criteria_match(self.mother_tasks_case, datetime.utcnow()))


class MigratedStatusTestCase(BaseMigratedCriteriaTestCase):

    __test__ = True

    @classmethod
    def person_case_update(cls):
        return {'migration_status': 'migrated'}

    @classmethod
    def should_exclude(cls):
        return True


class RegisteredStatusTestCase(BaseMigratedCriteriaTestCase):

    __test__ = True

    @classmethod
    def person_case_update(cls):
        return {'registered_status': 'not_registered'}

    @classmethod
    def should_exclude(cls):
        return True


class NormalStatusTestCase(BaseMigratedCriteriaTestCase):

    __test__ = True

    @classmethod
    def person_case_update(cls):
        return {}

    @classmethod
    def should_exclude(cls):
        return False
