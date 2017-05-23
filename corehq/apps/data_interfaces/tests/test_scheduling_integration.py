from contextlib import contextmanager
from casexml.apps.case.mock import CaseFactory
from corehq.apps.data_interfaces.models import (
    AutomaticUpdateRule,
    MatchPropertyDefinition,
    CreateScheduleInstanceActionDefinition,
)
from corehq.apps.domain.models import Domain
from corehq.apps.hqcase.utils import update_case
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.messaging.scheduling.models import AlertSchedule, TimedSchedule, SMSContent
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    get_case_timed_schedule_instances_for_schedule,
    delete_case_schedule_instance,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.sql_db.util import run_query_across_partitioned_databases
from datetime import datetime, date, time
from django.db.models import Q
from django.test import TestCase
from mock import patch


@contextmanager
def _create_case(domain, case_type):
    case = CaseFactory(domain).create_case(case_type=case_type)

    try:
        yield case
    finally:
        if should_use_sql_backend(domain):
            CaseAccessorSQL.hard_delete_cases(domain, [case.case_id])
        else:
            case.delete()


def _create_empty_rule(domain):
    return AutomaticUpdateRule.objects.create(
        domain=domain,
        name='test',
        case_type='person',
        active=True,
        deleted=False,
        filter_on_server_modified=False,
        server_modified_boundary=None,
        migrated=True,
        workflow=AutomaticUpdateRule.WORKFLOW_SCHEDULING,
    )


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

        for schedule in AlertSchedule.objects.filter(domain=self.domain):
            for event in schedule.memoized_events:
                event.content.delete()
                event.delete()

            schedule.delete()

        for schedule in TimedSchedule.objects.filter(domain=self.domain):
            for event in schedule.memoized_events:
                event.content.delete()
                event.delete()

            schedule.delete()

    @run_with_all_backends
    def test_timed_schedule_instance_creation(self):
        schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            time(9, 0),
            SMSContent(message={'en': 'Hello'})
        )

        rule = _create_empty_rule(self.domain)

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

        with _create_case(self.domain, 'person') as case, \
                patch('corehq.messaging.scheduling.util.utcnow') as utcnow_patch:

            utcnow_patch.return_value = datetime(2017, 5, 1, 7, 0)

            # Rule does not match, no instances created
            rule.run_rule(case, utcnow_patch.return_value)
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)

            update_case(self.domain, case.case_id, case_properties={'start_sending': 'Y'})
            case = CaseAccessors(self.domain).get_case(case.case_id)

            # Rule now matches. On the first iteration, the instance is created. On the second,
            # no new instance is created since it already exists.
            for minute in range(1, 3):
                utcnow_patch.return_value = datetime(2017, 5, 1, 7, minute)
                rule.run_rule(case, utcnow_patch.return_value)
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

            update_case(self.domain, case.case_id, case_properties={'start_sending': 'N'})
            case = CaseAccessors(self.domain).get_case(case.case_id)

            # Rule no longer matches. Instance should no longer exist.
            utcnow_patch.return_value = datetime(2017, 5, 1, 7, 3)
            rule.run_rule(case, utcnow_patch.return_value)
            instances = get_case_timed_schedule_instances_for_schedule(case.case_id, schedule)
            self.assertEqual(instances.count(), 0)
