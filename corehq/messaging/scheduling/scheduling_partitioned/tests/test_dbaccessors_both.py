from __future__ import absolute_import
from __future__ import unicode_literals
from corehq.form_processor.tests.utils import partitioned
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    CaseScheduleInstanceMixin,
    CaseAlertScheduleInstance,
    CaseTimedScheduleInstance,
)
from corehq.messaging.scheduling.tasks import delete_schedule_instances_for_cases
from corehq.sql_db.util import paginate_query_across_partitioned_databases
from datetime import datetime, date
from django.db.models import Q
from django.test import TestCase
import uuid


@partitioned
class SchedulingDBAccessorsTest(TestCase):

    domain = 'scheduling-dbaccessors-test'
    domain_2 = domain + '-x'

    def create_case_alert_schedule_instance(self, domain, case_id):
        instance = CaseAlertScheduleInstance(
            domain=domain,
            recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF,
            current_event_num=0,
            schedule_iteration_num=1,
            next_event_due=datetime(2018, 7, 1),
            active=True,
            alert_schedule_id=uuid.uuid4(),
            case_id=case_id,
            rule_id=1,
        )
        instance.save()
        self.addCleanup(instance.delete)

    def create_case_timed_schedule_instance(self, domain, case_id):
        instance = CaseTimedScheduleInstance(
            domain=domain,
            recipient_type=CaseScheduleInstanceMixin.RECIPIENT_TYPE_SELF,
            current_event_num=0,
            schedule_iteration_num=1,
            next_event_due=datetime(2018, 7, 1),
            active=True,
            timed_schedule_id=uuid.uuid4(),
            start_date=date(2018, 7, 1),
            case_id=case_id,
            rule_id=1,
        )
        instance.save()
        self.addCleanup(instance.delete)

    def get_case_schedule_instances_for_domain(self, domain):
        instances = list(paginate_query_across_partitioned_databases(CaseAlertScheduleInstance, Q(domain=domain)))
        instances.extend(paginate_query_across_partitioned_databases(CaseTimedScheduleInstance, Q(domain=domain)))
        return instances

    def test_delete_schedule_instances_for_cases(self):
        case_id_1 = uuid.uuid4().hex
        case_id_2 = uuid.uuid4().hex
        case_id_3 = uuid.uuid4().hex
        case_id_4 = uuid.uuid4().hex

        for domain, case_id in (
            (self.domain, case_id_1),
            (self.domain, case_id_2),
            (self.domain, case_id_3),
            (self.domain_2, case_id_4),
        ):
            self.create_case_alert_schedule_instance(domain, case_id)
            self.create_case_timed_schedule_instance(domain, case_id)

        self.assertEqual(len(self.get_case_schedule_instances_for_domain(self.domain)), 6)
        self.assertEqual(len(self.get_case_schedule_instances_for_domain(self.domain_2)), 2)

        delete_schedule_instances_for_cases(self.domain, [case_id_1, case_id_2])

        self.assertEqual(len(self.get_case_schedule_instances_for_domain(self.domain)), 2)
        self.assertEqual(len(self.get_case_schedule_instances_for_domain(self.domain_2)), 2)

        for instance in self.get_case_schedule_instances_for_domain(self.domain):
            self.assertEqual(instance.case_id, case_id_3)
