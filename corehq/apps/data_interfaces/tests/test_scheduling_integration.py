from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.apps.app_manager.models import (
    AdvancedModule,
    AdvancedForm,
    FormSchedule,
    ScheduleVisit,
    SchedulePhase,
    SchedulePhaseForm,
)
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
    VisitSchedulerIntegrationHelper,
)
from corehq.apps.data_interfaces.tests.util import create_case, create_empty_rule
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.messaging.scheduling.const import VISIT_WINDOW_START, VISIT_WINDOW_END, VISIT_WINDOW_DUE_DATE
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    TimedSchedule,
    TimedEvent,
    CasePropertyTimedEvent,
    SMSContent,
)
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    get_case_alert_schedule_instances_for_schedule,
    get_case_timed_schedule_instances_for_schedule,
    delete_case_schedule_instance,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.tasks import handle_case_timed_schedule_instance
from corehq.messaging.scheduling.tests.util import delete_alert_schedules, delete_timed_schedules
from corehq.messaging.tasks import run_messaging_rule, sync_case_for_messaging_rule
from corehq.sql_db.util import paginate_query_across_partitioned_databases
from datetime import datetime, date, time
from django.db.models import Q
from django.test import TestCase
from mock import patch, call
from six.moves import range


def get_visit_scheduler_module_and_form_for_test():
    form = AdvancedForm(
        schedule=FormSchedule(
            unique_id='form-unique-id-1',
            schedule_form_id='form1',
            enabled=True,
            visits=[
                ScheduleVisit(due=1, starts=-1, expires=1, repeats=False, increment=None),
                ScheduleVisit(due=7, starts=-2, expires=3, repeats=False, increment=None),
                ScheduleVisit(due=None, starts=None, expires=None, repeats=True, increment=14),
            ],
        )
    )

    module = AdvancedModule(
        schedule_phases=[
            SchedulePhase(anchor='edd', forms=[]),
            SchedulePhase(anchor='add', forms=[SchedulePhaseForm(form_id=form.unique_id)]),
        ],
        forms=[form],
    )

    return module, form


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

        for instance in paginate_query_across_partitioned_databases(
                CaseAlertScheduleInstance, Q(domain=self.domain)):
            delete_case_schedule_instance(instance)

        for instance in paginate_query_across_partitioned_databases(
                CaseTimedScheduleInstance, Q(domain=self.domain)):
            delete_case_schedule_instance(instance)

        delete_alert_schedules(self.domain)
        delete_timed_schedules(self.domain)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_instance_creation(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
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
    def test_alert_schedule_reset(self, utcnow_patch):
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
            recipients=(('CommCareUser', self.user.get_id),),
            reset_case_property_name='reset_property',
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2017, 5, 1, 7, 0)
        with create_case(self.domain, 'person') as case:
            # Rule does not match, no instances created
            instances = get_case_alert_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Make the rule match. On the first iteration, the instance is created. On the second,
            # nothing is changed.
            for minute in (1, 2):
                utcnow_patch.return_value = datetime(2017, 5, 1, 7, minute)
                update_case(self.domain, case.case_id,
                    case_properties={'start_sending': 'Y', 'reset_property': 'a'})

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
                self.assertEqual(instances[0].last_reset_case_property_value, 'a')
                self.assertTrue(instances[0].active)

            # Update the reset property, and the instance is reset.
            utcnow_patch.return_value = datetime(2017, 6, 1, 7, 0)
            update_case(self.domain, case.case_id, case_properties={'reset_property': 'b'})

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
            self.assertEqual(instances[0].next_event_due, datetime(2017, 6, 1, 7, 0))
            self.assertEqual(instances[0].last_reset_case_property_value, 'b')
            self.assertTrue(instances[0].active)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_reset(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
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

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.models.content.SMSContent.send')
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_stop_date_case_property(self, utcnow_patch, send_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'}),
            extra_options={'stop_date_case_property_name': 'stop_date'},
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),),
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2018, 7, 1, 7, 0)
        with create_case(self.domain, 'person') as case:
            # The case matches the rule and is setup to start sending
            update_case(self.domain, case.case_id, case_properties={'stop_date': '2018-07-03'})

            [instance] = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 7, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 1)
            self.assertEqual(instance.next_event_due, datetime(2018, 7, 1, 13, 0))
            self.assertTrue(instance.active)

            # Send the first event, and schedule the next event for the next day
            utcnow_patch.return_value = datetime(2018, 7, 1, 13, 1)
            handle_case_timed_schedule_instance(case.case_id, instance.schedule_instance_id)
            self.assertEqual(send_patch.call_count, 1)

            [instance] = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 7, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 2)
            self.assertEqual(instance.next_event_due, datetime(2018, 7, 2, 13, 0))
            self.assertTrue(instance.active)

            # Send the second event, and deactivate because the stop date has been reached
            utcnow_patch.return_value = datetime(2018, 7, 2, 13, 1)
            handle_case_timed_schedule_instance(case.case_id, instance.schedule_instance_id)
            self.assertEqual(send_patch.call_count, 2)

            [instance] = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 7, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 3)
            self.assertEqual(instance.next_event_due, datetime(2018, 7, 3, 13, 0))
            self.assertFalse(instance.active)

            # Update the stop date and the instance should be reactivated
            update_case(self.domain, case.case_id, case_properties={'stop_date': '2018-08-01'})

            [instance] = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 7, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 3)
            self.assertEqual(instance.next_event_due, datetime(2018, 7, 3, 13, 0))
            self.assertTrue(instance.active)

            # Update the stop date and the instance should be deactivated
            update_case(self.domain, case.case_id, case_properties={'stop_date': '2018-06-01'})

            [instance] = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 7, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 3)
            self.assertEqual(instance.next_event_due, datetime(2018, 7, 3, 13, 0))
            self.assertFalse(instance.active)

            # Update the stop date and the instance should be reactivated and fast-forwarded
            utcnow_patch.return_value = datetime(2018, 7, 4, 13, 1)
            update_case(self.domain, case.case_id, case_properties={'stop_date': '2018-08-01'})

            [instance] = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 7, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 5)
            self.assertEqual(instance.next_event_due, datetime(2018, 7, 5, 13, 0))
            self.assertTrue(instance.active)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_start_date_case_property(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'}),
            total_iterations=1,
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
            start_date_case_property='appointment_date',
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2017, 5, 1, 7, 0)
        with create_case(self.domain, 'person') as case:
            # Rule does not match, no instances created
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Make the rule match, but don't give a start date. No instances are created.
            update_case(self.domain, case.case_id, case_properties={'start_sending': 'Y'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Give a start date. On the first iteration, the instance is created. On the second,
            # no new instance is created since it already exists.
            for minute in [1, 2]:
                utcnow_patch.return_value = datetime(2017, 5, 1, 7, minute)
                update_case(self.domain, case.case_id, case_properties={'appointment_date': '2017-06-01'})

                instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
                self.assertEqual(instances.count(), 1)

                self.assertEqual(instances[0].case_id, case.case_id)
                self.assertEqual(instances[0].rule_id, rule.pk)
                self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
                self.assertEqual(instances[0].start_date, date(2017, 6, 1))
                self.assertEqual(instances[0].domain, self.domain)
                self.assertEqual(instances[0].recipient_type, 'CommCareUser')
                self.assertEqual(instances[0].recipient_id, self.user.get_id)
                self.assertEqual(instances[0].current_event_num, 0)
                self.assertEqual(instances[0].schedule_iteration_num, 1)
                self.assertEqual(instances[0].next_event_due, datetime(2017, 6, 1, 13, 0))
                self.assertTrue(instances[0].active)

            # Update start date. Instance is updated with new start date,
            update_case(self.domain, case.case_id, case_properties={'appointment_date': '2017-07-01'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 7, 1))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 7, 1, 13, 0))
            self.assertTrue(instances[0].active)

            # Set start date to the past. Instance is updated with new start date and is inactive
            update_case(self.domain, case.case_id, case_properties={'appointment_date': '2017-04-01'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 4, 1))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 2)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 4, 2, 13, 0))
            self.assertFalse(instances[0].active)

            # Give an invalid start date. Instance should no longer exist.
            update_case(self.domain, case.case_id, case_properties={'appointment_date': 'xyz'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_specific_start_date(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'}),
            total_iterations=1,
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        rule.add_criteria(
            MatchPropertyDefinition,
            property_name='start_sending',
            property_value='Y',
            match_type=MatchPropertyDefinition.MATCH_EQUAL,
        )

        action, definition = rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),),
            specific_start_date=date(2018, 3, 1),
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2018, 2, 28, 7, 0)
        with create_case(self.domain, 'person') as case:
            # Rule does not match, no instances created
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Make the rule match. On the first iteration, the instance is created. On the second,
            # no new instance is created since it already exists.
            for minute in [1, 2]:
                utcnow_patch.return_value = datetime(2018, 2, 28, 7, minute)
                update_case(self.domain, case.case_id, case_properties={'start_sending': 'Y'})

                instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
                self.assertEqual(instances.count(), 1)

                self.assertEqual(instances[0].case_id, case.case_id)
                self.assertEqual(instances[0].rule_id, rule.pk)
                self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
                self.assertEqual(instances[0].start_date, date(2018, 3, 1))
                self.assertEqual(instances[0].domain, self.domain)
                self.assertEqual(instances[0].recipient_type, 'CommCareUser')
                self.assertEqual(instances[0].recipient_id, self.user.get_id)
                self.assertEqual(instances[0].current_event_num, 0)
                self.assertEqual(instances[0].schedule_iteration_num, 1)
                self.assertEqual(instances[0].next_event_due, datetime(2018, 3, 1, 14, 0))
                self.assertTrue(instances[0].active)

            # Update start date. Instance is updated with new start date.
            definition.specific_start_date = date(2018, 4, 1)
            definition.save()
            AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

            sync_case_for_messaging_rule(self.domain, case.case_id, rule.pk)
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2018, 4, 1))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2018, 4, 1, 13, 0))
            self.assertTrue(instances[0].active)

            # Set start date to the past. Instance is updated with new start date and is inactive.
            definition.specific_start_date = date(2018, 2, 1)
            definition.save()
            AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

            sync_case_for_messaging_rule(self.domain, case.case_id, rule.pk)
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2018, 2, 1))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 2)
            self.assertEqual(instances[0].next_event_due, datetime(2018, 2, 2, 14, 0))
            self.assertFalse(instances[0].active)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_timed_schedule_case_property_timed_event(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            CasePropertyTimedEvent(case_property_name='reminder_time'),
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
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2017, 5, 1, 7, 0)
        with create_case(self.domain, 'person') as case:
            # Rule does not match, no instances created
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            # Make the rule match, but don't give a preferred time. Default scheduling time is used.
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
            self.assertEqual(instances[0].next_event_due, datetime(2017, 5, 1, 16, 0))
            self.assertTrue(instances[0].active)

            # Update the preferred time, and the schedule should recalculate
            update_case(self.domain, case.case_id, case_properties={'reminder_time': '09:00'})
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

            # Update the preferred time to a bad value and the default time is used again.
            update_case(self.domain, case.case_id, case_properties={'reminder_time': 'x'})
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
            self.assertEqual(instances[0].next_event_due, datetime(2017, 5, 1, 16, 0))
            self.assertTrue(instances[0].active)

    @run_with_all_backends
    @patch('corehq.apps.data_interfaces.models.VisitSchedulerIntegrationHelper.get_visit_scheduler_module_and_form')
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_visit_scheduler_integration(self, utcnow_patch, module_and_form_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'}),
            total_iterations=1,
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        _, definition = rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),)
        )

        module, form = get_visit_scheduler_module_and_form_for_test()

        definition.set_scheduler_module_info(CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(
            enabled=True,
            app_id='n/a for test',
            form_unique_id=form.unique_id,
            visit_number=1,
            window_position=VISIT_WINDOW_START,
        ))

        definition.save()

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        utcnow_patch.return_value = datetime(2017, 8, 1, 7, 0)
        module_and_form_patch.return_value = module, form

        with create_case(self.domain, 'person') as case:
            # Schedule phase does not match, nothing is scheduled
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            update_case(self.domain, case.case_id,
                case_properties={'add': '2017-08-01', 'current_schedule_phase': '2'})

            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 8, 6))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 8, 6, 13, 0))
            self.assertTrue(instances[0].active)

            # If the anchor date gets updated (due to correction, for example), the schedule recalculates
            update_case(self.domain, case.case_id, case_properties={'add': '2017-08-10'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 8, 15))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 8, 15, 13, 0))
            self.assertTrue(instances[0].active)

            # If the anchor date is in the past, the schedule instance is deactivated
            update_case(self.domain, case.case_id, case_properties={'add': '2017-07-01'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 7, 6))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 2)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 7, 7, 13, 0))
            self.assertFalse(instances[0].active)

            # If the anchor date is reset, the schedule instance is reactivated
            update_case(self.domain, case.case_id, case_properties={'add': '2017-08-01'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 8, 6))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 8, 6, 13, 0))
            self.assertTrue(instances[0].active)

            # Making an arbitrary update doesn't cause any recalculating to happen
            with patch('corehq.messaging.scheduling.scheduling_partitioned.models.AbstractTimedScheduleInstance.recalculate_schedule') as recalculate_patch:
                update_case(self.domain, case.case_id, case_properties={'new_property': 'new value'})
                self.assertEqual(recalculate_patch.call_count, 0)

            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 8, 6))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 8, 6, 13, 0))
            self.assertTrue(instances[0].active)

            # Terminate the schedule, no more schedule instances should be scheduled
            update_case(self.domain, case.case_id, case_properties={'current_schedule_phase': '-1'})
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_start_offset(self, utcnow_patch):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'}),
            start_offset=2,
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),),
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)
        utcnow_patch.return_value = datetime(2017, 8, 1, 15, 0)

        with create_case(self.domain, 'person') as case:
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 8, 1))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 8, 3, 13, 0))
            self.assertEqual(instances[0].schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instances[0].active)

            # Change the schedule's start offset and force a case update to reprocess the schedule instance.
            # The start date should not change, but the schedule instance should respond to the new start offset
            # by calculating a new next_event_due timestamp.
            schedule.start_offset = 5
            schedule.save()
            schedule = TimedSchedule.objects.get(schedule_id=schedule.schedule_id)
            utcnow_patch.return_value = datetime(2017, 8, 4, 7, 0)
            update_case(self.domain, case.case_id, case_properties={'new_property': 'new value'})

            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 8, 1))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 8, 6, 13, 0))
            self.assertEqual(instances[0].schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instances[0].active)

            # Making another arbitrary update doesn't cause any recalculating to happen
            with patch('corehq.messaging.scheduling.scheduling_partitioned.models.AbstractTimedScheduleInstance.recalculate_schedule') as recalculate_patch:
                update_case(self.domain, case.case_id, case_properties={'new_property': 'new value 2'})
                self.assertEqual(recalculate_patch.call_count, 0)

            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)

            self.assertEqual(instances[0].case_id, case.case_id)
            self.assertEqual(instances[0].rule_id, rule.pk)
            self.assertEqual(instances[0].timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instances[0].start_date, date(2017, 8, 1))
            self.assertEqual(instances[0].domain, self.domain)
            self.assertEqual(instances[0].recipient_type, 'CommCareUser')
            self.assertEqual(instances[0].recipient_id, self.user.get_id)
            self.assertEqual(instances[0].current_event_num, 0)
            self.assertEqual(instances[0].schedule_iteration_num, 1)
            self.assertEqual(instances[0].next_event_due, datetime(2017, 8, 6, 13, 0))
            self.assertEqual(instances[0].schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instances[0].active)

    @run_with_all_backends
    @patch('corehq.messaging.tasks.sync_case_for_messaging_rule.delay')
    def test_run_messaging_rule(self, task_patch):
        schedule = AlertSchedule.create_simple_alert(
            self.domain,
            SMSContent(message={'en': 'Hello'})
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            alert_schedule_id=schedule.schedule_id,
            recipients=(('Self', None),),
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        with create_case(self.domain, 'person') as case1, create_case(self.domain, 'person') as case2:
            run_messaging_rule(self.domain, rule.pk)
            self.assertEqual(task_patch.call_count, 2)
            task_patch.assert_has_calls(
                [
                    call(self.domain, case1.case_id, rule.pk),
                    call(self.domain, case2.case_id, rule.pk),
                ],
                any_order=True
            )

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.models.content.SMSContent.send')
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_next_available_daily_slot(self, utcnow_patch, send_patch):

        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'}),
            total_iterations=2,
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        # Leave all start date information blank so it schedules for the next available daily slot
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),),
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        # It's 3/1 at 7am local time; the schedule instance gets scheduled for the same day
        utcnow_patch.return_value = datetime(2018, 3, 1, 12, 0)
        with create_case(self.domain, 'person') as case:
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)
            instance = instances[0]
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 3, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 1)
            self.assertEqual(instance.next_event_due, datetime(2018, 3, 1, 14, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

        # It's 3/1 at 10am local time; the schedule instance gets scheduled for the next day
        utcnow_patch.return_value = datetime(2018, 3, 1, 15, 0)
        with create_case(self.domain, 'person') as case:
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)
            instance = instances[0]
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 3, 2))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 1)
            self.assertEqual(instance.next_event_due, datetime(2018, 3, 2, 14, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

            # Fire the event
            utcnow_patch.return_value = datetime(2018, 3, 2, 14, 1)
            instance.handle_current_event()
            self.assertEqual(send_patch.call_count, 1)

            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 3, 2))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 2)
            self.assertEqual(instance.next_event_due, datetime(2018, 3, 3, 14, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.models.content.SMSContent.send')
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_next_available_weekly_slot(self, utcnow_patch, send_patch):

        # Mondays with the week starting on Monday
        schedule = TimedSchedule.create_simple_weekly_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            SMSContent(message={'en': 'Hello'}),
            [0],
            0,
            total_iterations=2,
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        # Leave all start date information blank so it schedules for the next available weekly slot
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),),
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        # It's 3/4 at 10pm local time; the schedule instance gets scheduled for the same week
        utcnow_patch.return_value = datetime(2018, 3, 5, 3, 0)
        with create_case(self.domain, 'person') as case:
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)
            instance = instances[0]
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 3, 4))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 1)
            self.assertEqual(instance.next_event_due, datetime(2018, 3, 5, 14, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

        # It's 3/5 at 10pm local time; the schedule instance gets scheduled for the next week
        utcnow_patch.return_value = datetime(2018, 3, 6, 3, 0)
        with create_case(self.domain, 'person') as case:
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)
            instance = instances[0]
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 3, 12))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 1)
            self.assertEqual(instance.next_event_due, datetime(2018, 3, 12, 13, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

            # Fire the event
            utcnow_patch.return_value = datetime(2018, 3, 12, 13, 1)
            instance.handle_current_event()
            self.assertEqual(send_patch.call_count, 1)

            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 3, 12))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 2)
            self.assertEqual(instance.next_event_due, datetime(2018, 3, 19, 13, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

    @run_with_all_backends
    @patch('corehq.messaging.scheduling.models.content.SMSContent.send')
    @patch('corehq.messaging.scheduling.util.utcnow')
    def test_next_available_monthly_slot(self, utcnow_patch, send_patch):

        schedule = TimedSchedule.create_simple_monthly_schedule(
            self.domain,
            TimedEvent(time=time(9, 0)),
            [15],
            SMSContent(message={'en': 'Hello'}),
            total_iterations=2,
        )

        rule = create_empty_rule(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        # Leave all start date information blank so it schedules for the next available monthly slot
        rule.add_action(
            CreateScheduleInstanceActionDefinition,
            timed_schedule_id=schedule.schedule_id,
            recipients=(('CommCareUser', self.user.get_id),),
        )

        AutomaticUpdateRule.clear_caches(self.domain, AutomaticUpdateRule.WORKFLOW_SCHEDULING)

        # It's 3/4 at 5pm local time; the schedule instance gets scheduled for the same month
        utcnow_patch.return_value = datetime(2018, 3, 4, 22, 0)
        with create_case(self.domain, 'person') as case:
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)
            instance = instances[0]
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 3, 4))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 1)
            self.assertEqual(instance.next_event_due, datetime(2018, 3, 15, 13, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

        # It's 3/16 at 5pm local time; the schedule instance gets scheduled for the next month
        utcnow_patch.return_value = datetime(2018, 3, 16, 21, 0)
        with create_case(self.domain, 'person') as case:
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 1)
            instance = instances[0]
            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 4, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 1)
            self.assertEqual(instance.next_event_due, datetime(2018, 4, 15, 13, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)

            # Fire the event
            utcnow_patch.return_value = datetime(2018, 4, 15, 13, 1)
            instance.handle_current_event()
            self.assertEqual(send_patch.call_count, 1)

            self.assertEqual(instance.case_id, case.case_id)
            self.assertEqual(instance.rule_id, rule.pk)
            self.assertEqual(instance.timed_schedule_id, schedule.schedule_id)
            self.assertEqual(instance.start_date, date(2018, 4, 1))
            self.assertEqual(instance.domain, self.domain)
            self.assertEqual(instance.recipient_type, 'CommCareUser')
            self.assertEqual(instance.recipient_id, self.user.get_id)
            self.assertEqual(instance.current_event_num, 0)
            self.assertEqual(instance.schedule_iteration_num, 2)
            self.assertEqual(instance.next_event_due, datetime(2018, 5, 15, 13, 0))
            self.assertEqual(instance.schedule_revision, schedule.get_schedule_revision())
            self.assertTrue(instance.active)


class VisitSchedulerIntegrationHelperTestCase(TestCase):
    domain = 'visit-scheduler-integration-helper'

    @classmethod
    def setUpClass(cls):
        cls.module, cls.form = get_visit_scheduler_module_and_form_for_test()
        super(VisitSchedulerIntegrationHelperTestCase, cls).setUpClass()

    def get_helper(self, case, visit_number=2, window_position=VISIT_WINDOW_START):
        return VisitSchedulerIntegrationHelper(
            case,
            CreateScheduleInstanceActionDefinition.SchedulerModuleInfo(
                enabled=True,
                app_id='n/a for test',
                form_unique_id=self.form.unique_id,
                visit_number=visit_number,
                window_position=window_position,
            )
        )

    def test_get_visit_scheduler_form_phase(self):
        with create_case(self.domain, 'person') as case:
            phase_num, phase = self.get_helper(case).get_visit_scheduler_form_phase(self.module)
            self.assertEqual(phase_num, 2)
            self.assertEqual(phase.to_json(), self.module.schedule_phases[1].to_json())

    def test_calculate_window_date(self):
        with create_case(self.domain, 'person') as case:
            helper = self.get_helper(case, window_position=VISIT_WINDOW_START)
            self.assertEqual(
                helper.calculate_window_date(self.form.schedule.visits[1], date(2017, 8, 1)),
                date(2017, 7, 30)
            )

            helper = self.get_helper(case, window_position=VISIT_WINDOW_DUE_DATE)
            self.assertEqual(
                helper.calculate_window_date(self.form.schedule.visits[1], date(2017, 8, 1)),
                date(2017, 8, 1)
            )

            helper = self.get_helper(case, window_position=VISIT_WINDOW_END)
            self.assertEqual(
                helper.calculate_window_date(self.form.schedule.visits[1], date(2017, 8, 1)),
                date(2017, 8, 4)
            )

    @run_with_all_backends
    def test_get_case_current_schedule_phase(self):
        with create_case(self.domain, 'person') as case:
            helper = self.get_helper(case)
            self.assertIsNone(helper.get_case_current_schedule_phase())

            update_case(self.domain, case.case_id, case_properties={'current_schedule_phase': '2'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            helper = self.get_helper(case)
            self.assertEqual(helper.get_case_current_schedule_phase(), 2)

    def test_get_visit(self):
        with create_case(self.domain, 'person') as case:
            helper = self.get_helper(case, visit_number=1)
            self.assertEqual(
                helper.get_visit(self.form).to_json(),
                self.form.schedule.visits[1].to_json()
            )

            # Repeat visits aren't supported
            helper = self.get_helper(case, visit_number=2)
            with self.assertRaises(VisitSchedulerIntegrationHelper.VisitSchedulerIntegrationException):
                helper.get_visit(self.form)

            # Index out of range
            helper = self.get_helper(case, visit_number=999)
            with self.assertRaises(VisitSchedulerIntegrationHelper.VisitSchedulerIntegrationException):
                helper.get_visit(self.form)

    @run_with_all_backends
    def test_get_anchor_date(self):
        with create_case(self.domain, 'person') as case:
            helper = self.get_helper(case)
            with self.assertRaises(VisitSchedulerIntegrationHelper.VisitSchedulerIntegrationException):
                helper.get_anchor_date('add')

            update_case(self.domain, case.case_id, case_properties={'add': '2017-08-01'})
            case = CaseAccessors(self.domain).get_case(case.case_id)
            helper = self.get_helper(case)
            self.assertEqual(helper.get_anchor_date('add'), date(2017, 8, 1))
