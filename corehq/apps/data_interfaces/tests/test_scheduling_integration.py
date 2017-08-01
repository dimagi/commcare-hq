from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.data_interfaces.tests.util import create_case, create_empty_rule
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule, SMSContent
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    get_case_alert_schedule_instances_for_schedule,
    get_case_timed_schedule_instances_for_schedule,
    delete_case_schedule_instance,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.tests.util import delete_alert_schedules, delete_timed_schedules
from corehq.sql_db.util import run_query_across_partitioned_databases
from datetime import datetime, date, time
from django.db.models import Q
from django.test import TestCase
from mock import patch


class CaseRuleSchedulingIntegrationTest(TestCase):
    domain = 'case-rule-scheduling-test'

    @classmethod
    def setUpClass(cls):
        super(CaseRuleSchedulingIntegrationTest, cls).setUpClass()
        cls.domain_obj = Domain(
            name=cls.domain,
            default_timezone='America/New_York',
        )
        cls.domain_obj.save()
        cls.user = CommCareUser.create(cls.domain, 'test1', 'abc')

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain_obj.delete()
        super(CaseRuleSchedulingIntegrationTest, cls).tearDownClass()

    def tearDown(self):
        for rule in AutomaticUpdateRule.objects.filter(domain=self.domain):
            rule.hard_delete()

        for instance in run_query_across_partitioned_databases(CaseAlertScheduleInstance, Q(domain=self.domain)):
            delete_case_schedule_instance(instance)

        for instance in run_query_across_partitioned_databases(CaseTimedScheduleInstance, Q(domain=self.domain)):
            delete_case_schedule_instance(instance)

        delete_alert_schedules(self.domain)
        delete_timed_schedules(self.domain)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_instance_creation(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            time(9, 0),
            SMSContent(message={'en': 'Hello'})
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='start_sending',
            property_value='Y',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),)
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2017, 5, 1, 7, 0)
        with create_case(self.domain, 'person') as case:
            # Rule does not match, no instances created
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Make the rule match. On the first iteration, the instance is created. On the second,
            # no new instance is created since it already exists.
            for minute in [1, 2]:
                utcnow_patch.return_value = datetime(2017, 5, 1, 7, minute)
                update_case(self.domain, case.case_id, case_properties={'start_sending': 'Y'})

                instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
                self.assertEqual(instances.count(), 1)

                self.assertEqual(instances[0].case_id, case.case_id)
                self.assertEqual(instances[0].rule_id, rule.pk)
                self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
                self.assertEqual(instances[0].start_date, date(2017, 5, 1))
                self.assertEqual(instances[0].domain, self.domain)
                self.assertEqual(instances[0].recipient_type, 'CommCareUser')
                self.assertEqual(instances[0].recipient_id, self.user.get_id)
                self.assertEqual(instances[0].current_event_num, 0)
                self.assertEqual(instances[0].schedule_iteration_num, 1)
                self.assertEqual(instances[0].next_event_due, datetime(2017, 5, 1, 13, 0))
                self.assertTrue(instances[0].active)

            # Make the rule not match. Instance should no longer exist.
            utcnow_patch.return_value = datetime(2017, 5, 1, 7, 3)
            update_case(self.domain, case.case_id, case_properties={'start_sending': 'N'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_alert_schedule_instance_creation(self, utcnow_patch):
        schedule = AlertSchedule.create_simple_alert(
            self.domain,
            SMSContent(message={'en': 'Hello'})
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='start_sending',
            property_value='Y',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            alert_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),)
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2017, 5, 1, 7, 0)
        with create_case(self.domain, 'person') as case:
            # Rule does not match, no instances created
            instances = get_case_alert_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Make the rule match. On the first iteration, the instance is created. On the second,
            # no new instance is created since it already exists.
            for minute in range(1, 3):
                utcnow_patch.return_value = datetime(2017, 5, 1, 7, minute)
                update_case(self.domain, case.case_id, case_properties={'start_sending': 'Y'})

                instances = get_case_alert_schedule_instances_for_schedule(case.case_id, schedule)
                self.assertEqual(instances.count(), 1)

                self.assertEqual(instances[0].case_id, case.case_id)
                self.assertEqual(instances[0].rule_id, rule.pk)
                self.assertEqual(instances[0].alert_schedule_id, schedule.schedule_id)
                self.assertEqual(instances[0].domain, self.domain)
                self.assertEqual(instances[0].recipient_type, 'CommCareUser')
                self.assertEqual(instances[0].recipient_id, self.user.get_id)
                self.assertEqual(instances[0].current_event_num, 0)
                self.assertEqual(instances[0].schedule_iteration_num, 1)
                self.assertEqual(instances[0].next_event_due, datetime(2017, 5, 1, 7, 1))
                self.assertTrue(instances[0].active)

            # Make the rule not match. Instance should no longer exist.
            utcnow_patch.return_value = datetime(2017, 5, 1, 7, 3)
            update_case(self.domain, case.case_id, case_properties={'start_sending': 'N'})

            instances = get_case_alert_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_reset(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            time(9, 0),
            SMSContent(message={'en': 'Hello'})
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='start_sending',
            property_value='Y',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),),
            reset_case_property_name='reset_property',
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2017, 5, 1, 7, 0)
        with create_case(self.domain, 'person') as case:
            # Rule does not match, no instances created
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Make the rule match. On the first iteration, the instance is created. On the second,
            # no new instance is created since it already exists.
            for day in [1, 2]:
                utcnow_patch.return_value = datetime(2017, 5, day, 20, 0)
                update_case(self.domain, case.case_id,
                    case_properties={'start_sending': 'Y', 'reset_property': '1'})

                instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
                self.assertEqual(instances.count(), 1)

                self.assertEqual(instances[0].case_id, case.case_id)
                self.assertEqual(instances[0].rule_id, rule.pk)
                self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
                self.assertEqual(instances[0].start_date, date(2017, 5, 2))
                self.assertEqual(instances[0].domain, self.domain)
                self.assertEqual(instances[0].recipient_type, 'CommCareUser')
                self.assertEqual(instances[0].recipient_id, self.user.get_id)
                self.assertEqual(instances[0].current_event_num, 0)
                self.assertEqual(instances[0].schedule_iteration_num, 1)
                self.assertEqual(instances[0].next_event_due, datetime(2017, 5, 2, 13, 0))
                self.assertTrue(instances[0].active)

            # Change the value of 'reset_property', and the start date should be reset
            utcnow_patch.return_value = datetime(2017, 5, 2, 20, 0)
            update_case(self.domain, case.case_id, case_properties={'reset_property': '2'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 5, 3))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 5, 3, 13, 0))
            self.assertTrue(instances[0].active)

            # Make the rule not match. Instance should no longer exist.
            utcnow_patch.return_value = datetime(2017, 5, 2, 20, 0)
            update_case(self.domain, case.case_id, case_properties={'start_sending': 'N'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)
