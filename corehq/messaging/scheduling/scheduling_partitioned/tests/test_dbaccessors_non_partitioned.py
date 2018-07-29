from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from corehq.form_processor.tests.utils import only_run_with_non_partitioned_database
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    get_alert_schedule_instance,
    get_timed_schedule_instance,
    save_alert_schedule_instance,
    save_timed_schedule_instance,
    delete_alert_schedule_instance,
    delete_timed_schedule_instance,
    get_active_schedule_instance_ids,
    get_alert_schedule_instances_for_schedule,
    get_timed_schedule_instances_for_schedule,
)
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    TimedSchedule,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
)
from corehq.util.exceptions import AccessRestricted
from datetime import datetime, date
from django.test import TestCase


@only_run_with_non_partitioned_database
class BaseSchedulingNontPartitionedDBAccessorsTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseSchedulingNontPartitionedDBAccessorsTest, cls).setUpClass()
        cls.domain = 'scheduling-non-partitioned-test'
        cls.db = 'default'

    @classmethod
    def make_alert_schedule_instance(cls, schedule_instance_id=None, schedule_id=None, active=True):
        return AlertScheduleInstance(
            schedule_instance_id=schedule_instance_id or uuid.uuid4(),
            domain=cls.domain,
            recipient_type='CommCareUser',
            recipient_id='user-id',
            current_event_num=0,
            schedule_iteration_num=1,
            next_event_due=datetime(2017, 3, 1),
            active=active,
            alert_schedule_id=schedule_id or uuid.uuid4(),
        )

    @classmethod
    def make_timed_schedule_instance(cls, schedule_instance_id=None, schedule_id=None, active=True):
        return TimedScheduleInstance(
            schedule_instance_id=schedule_instance_id or uuid.uuid4(),
            domain=cls.domain,
            recipient_type='CommCareUser',
            recipient_id='user-id',
            current_event_num=0,
            schedule_iteration_num=1,
            next_event_due=datetime(2017, 3, 1),
            active=active,
            timed_schedule_id=schedule_id or uuid.uuid4(),
            start_date=date(2017, 3, 1),
        )


class TestSchedulingNonPartitionedDBAccessorsGetAndSave(BaseSchedulingNontPartitionedDBAccessorsTest):

    def tearDown(self):
        AlertScheduleInstance.objects.using(self.db).filter(domain=self.domain).delete()
        TimedScheduleInstance.objects.using(self.db).filter(domain=self.domain).delete()

    def test_save_alert_schedule_instance(self):
        self.assertEqual(AlertScheduleInstance.objects.using(self.db).count(), 0)

        instance = self.make_alert_schedule_instance()
        save_alert_schedule_instance(instance)

        self.assertEqual(AlertScheduleInstance.objects.using(self.db).count(), 1)

    def test_save_timed_schedule_instance(self):
        self.assertEqual(TimedScheduleInstance.objects.using(self.db).count(), 0)

        instance = self.make_timed_schedule_instance()
        save_timed_schedule_instance(instance)

        self.assertEqual(TimedScheduleInstance.objects.using(self.db).count(), 1)

    def test_get_alert_schedule_instance(self):
        instance1 = self.make_alert_schedule_instance()
        save_alert_schedule_instance(instance1)

        instance2 = get_alert_schedule_instance(instance1.schedule_instance_id)
        self.assertTrue(isinstance(instance2, AlertScheduleInstance))
        self.assertEqual(instance1.schedule_instance_id, instance2.schedule_instance_id)

        with self.assertRaises(AlertScheduleInstance.DoesNotExist):
            get_alert_schedule_instance(uuid.uuid4())

    def test_get_timed_schedule_instance(self):
        instance1 = self.make_timed_schedule_instance()
        save_timed_schedule_instance(instance1)

        instance2 = get_timed_schedule_instance(instance1.schedule_instance_id)
        self.assertTrue(isinstance(instance2, TimedScheduleInstance))
        self.assertEqual(instance1.schedule_instance_id, instance2.schedule_instance_id)

        with self.assertRaises(TimedScheduleInstance.DoesNotExist):
            get_timed_schedule_instance(uuid.uuid4())


class TestSchedulingNonPartitionedDBAccessorsDeleteAndFilter(BaseSchedulingNontPartitionedDBAccessorsTest):

    @classmethod
    def setUpClass(cls):
        super(TestSchedulingNonPartitionedDBAccessorsDeleteAndFilter, cls).setUpClass()
        cls.schedule_id1 = uuid.uuid4()
        cls.schedule_id2 = uuid.uuid4()
        cls.uuid1 = uuid.uuid4()
        cls.uuid2 = uuid.uuid4()
        cls.uuid3 = uuid.uuid4()
        cls.uuid4 = uuid.uuid4()
        cls.uuid5 = uuid.uuid4()
        cls.uuid6 = uuid.uuid4()

    def setUp(self):
        self.alert_instance1 = self.make_alert_schedule_instance(self.uuid1)
        save_alert_schedule_instance(self.alert_instance1)

        self.alert_instance2 = self.make_alert_schedule_instance(self.uuid2, schedule_id=self.schedule_id1)
        save_alert_schedule_instance(self.alert_instance2)

        self.alert_instance3 = self.make_alert_schedule_instance(self.uuid3, schedule_id=self.schedule_id1,
            active=False)
        save_alert_schedule_instance(self.alert_instance3)

        self.timed_instance1 = self.make_timed_schedule_instance(self.uuid4)
        save_timed_schedule_instance(self.timed_instance1)

        self.timed_instance2 = self.make_timed_schedule_instance(self.uuid5, schedule_id=self.schedule_id2)
        save_timed_schedule_instance(self.timed_instance2)

        self.timed_instance3 = self.make_timed_schedule_instance(self.uuid6, schedule_id=self.schedule_id2,
            active=False)
        save_timed_schedule_instance(self.timed_instance3)

    def tearDown(self):
        AlertScheduleInstance.objects.using(self.db).filter(domain=self.domain).delete()
        TimedScheduleInstance.objects.using(self.db).filter(domain=self.domain).delete()

    def test_delete_alert_schedule_instance(self):
        self.assertEqual(AlertScheduleInstance.objects.using(self.db).count(), 3)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db).count(), 3)

        delete_alert_schedule_instance(self.alert_instance1)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db).count(), 2)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db).count(), 3)

        with self.assertRaises(AlertScheduleInstance.DoesNotExist):
            get_alert_schedule_instance(self.uuid1)

    def test_delete_timed_schedule_instance(self):
        self.assertEqual(AlertScheduleInstance.objects.using(self.db).count(), 3)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db).count(), 3)

        delete_timed_schedule_instance(self.timed_instance1)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db).count(), 3)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db).count(), 2)

        with self.assertRaises(TimedScheduleInstance.DoesNotExist):
            get_timed_schedule_instance(self.uuid4)

    def test_get_active_alert_schedule_instance_ids(self):
        self.assertItemsEqual(
            get_active_schedule_instance_ids(
                AlertScheduleInstance,
                datetime(2017, 4, 1),
                due_after=datetime(2017, 2, 1),
            ),
            [(self.domain, self.alert_instance1.schedule_instance_id, self.alert_instance1.next_event_due),
             (self.domain, self.alert_instance2.schedule_instance_id, self.alert_instance2.next_event_due)]
        )

        self.assertItemsEqual(
            get_active_schedule_instance_ids(
                AlertScheduleInstance,
                datetime(2016, 4, 1),
                due_after=datetime(2016, 2, 1),
            ),
            []
        )

    def test_get_active_timed_schedule_instance_ids(self):
        self.assertItemsEqual(
            get_active_schedule_instance_ids(
                TimedScheduleInstance,
                datetime(2017, 4, 1),
                due_after=datetime(2017, 2, 1),
            ),
            [(self.domain, self.timed_instance1.schedule_instance_id, self.timed_instance1.next_event_due),
             (self.domain, self.timed_instance2.schedule_instance_id, self.timed_instance2.next_event_due)],
        )

        self.assertItemsEqual(
            get_active_schedule_instance_ids(
                TimedScheduleInstance,
                datetime(2016, 4, 1),
                due_after=datetime(2016, 2, 1),
            ),
            []
        )

    def test_get_alert_schedule_instances_for_schedule(self):
        self.assertItemsEqual(
            get_alert_schedule_instances_for_schedule(AlertSchedule(schedule_id=self.schedule_id1)),
            [self.alert_instance2, self.alert_instance3]
        )

    def test_get_timed_schedule_instances_for_schedule(self):
        self.assertItemsEqual(
            get_timed_schedule_instances_for_schedule(TimedSchedule(schedule_id=self.schedule_id2)),
            [self.timed_instance2, self.timed_instance3]
        )
