from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.form_processor.tests.utils import only_run_with_partitioned_database
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
from corehq.sql_db.config import partition_config
from corehq.sql_db.tests.utils import DefaultShardingTestConfigMixIn
from datetime import datetime, date
from django.test import TestCase


@only_run_with_partitioned_database
class BaseSchedulingPartitionedDBAccessorsTest(DefaultShardingTestConfigMixIn, TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseSchedulingPartitionedDBAccessorsTest, cls).setUpClass()
        cls.domain = 'scheduling-partitioned-models-test'

    @classmethod
    def make_alert_schedule_instance(cls, schedule_instance_id, schedule_id=None, active=True, domain=None):
        domain = domain or cls.domain
        return AlertScheduleInstance(
            schedule_instance_id=schedule_instance_id,
            domain=domain,
            recipient_type='CommCareUser',
            recipient_id='user-id',
            current_event_num=0,
            schedule_iteration_num=1,
            next_event_due=datetime(2017, 3, 1),
            active=active,
            alert_schedule_id=schedule_id or uuid.uuid4(),
        )

    @classmethod
    def make_timed_schedule_instance(cls, schedule_instance_id, schedule_id=None, active=True):
        return TimedScheduleInstance(
            schedule_instance_id=schedule_instance_id,
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


class TestSchedulingPartitionedDBAccessorsGetAndSave(BaseSchedulingPartitionedDBAccessorsTest):

    @classmethod
    def setUpClass(cls):
        super(TestSchedulingPartitionedDBAccessorsGetAndSave, cls).setUpClass()
        cls.p1_uuid = uuid.UUID('9d3a283a-25b6-4116-8846-d0fc8f04f50f')
        cls.p2_uuid = uuid.UUID('8440dbd6-61b1-4b2f-a310-7e1768902d04')

    def tearDown(self):
        for db in partition_config.get_form_processing_dbs():
            AlertScheduleInstance.objects.using(db).filter(domain=self.domain).delete()
            TimedScheduleInstance.objects.using(db).filter(domain=self.domain).delete()

    def test_uuids_used(self):
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p1_uuid), self.db1)
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p2_uuid), self.db2)

    def test_save_alert_schedule_instance(self):
        self.assertEqual(AlertScheduleInstance.objects.using(partition_config.get_proxy_db()).count(), 0)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db1).count(), 0)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db2).count(), 0)

        instance = self.make_alert_schedule_instance(self.p1_uuid)
        save_alert_schedule_instance(instance)

        self.assertEqual(AlertScheduleInstance.objects.using(partition_config.get_proxy_db()).count(), 0)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db1).count(), 1)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db2).count(), 0)

    def test_save_timed_schedule_instance(self):
        self.assertEqual(TimedScheduleInstance.objects.using(partition_config.get_proxy_db()).count(), 0)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db1).count(), 0)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db2).count(), 0)

        instance = self.make_timed_schedule_instance(self.p2_uuid)
        save_timed_schedule_instance(instance)

        self.assertEqual(TimedScheduleInstance.objects.using(partition_config.get_proxy_db()).count(), 0)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db1).count(), 0)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db2).count(), 1)

    def test_get_alert_schedule_instance(self):
        self.test_save_alert_schedule_instance()
        instance = get_alert_schedule_instance(self.p1_uuid)
        self.assertTrue(isinstance(instance, AlertScheduleInstance))
        self.assertEqual(instance.schedule_instance_id, self.p1_uuid)

        with self.assertRaises(AlertScheduleInstance.DoesNotExist):
            get_alert_schedule_instance(uuid.uuid4())

    def test_get_timed_schedule_instance(self):
        self.test_save_timed_schedule_instance()
        instance = get_timed_schedule_instance(self.p2_uuid)
        self.assertTrue(isinstance(instance, TimedScheduleInstance))
        self.assertEqual(instance.schedule_instance_id, self.p2_uuid)

        with self.assertRaises(TimedScheduleInstance.DoesNotExist):
            get_timed_schedule_instance(uuid.uuid4())


class TestSchedulingPartitionedDBAccessorsDeleteAndFilter(BaseSchedulingPartitionedDBAccessorsTest):

    @classmethod
    def setUpClass(cls):
        super(TestSchedulingPartitionedDBAccessorsDeleteAndFilter, cls).setUpClass()
        cls.schedule_id1 = uuid.uuid4()
        cls.schedule_id2 = uuid.uuid4()
        cls.p1_uuid1 = uuid.UUID('a1a387cf-b362-481c-9104-a5dfb5b5d28a')
        cls.p1_uuid2 = uuid.UUID('e5193227-a148-4389-97e7-14615bfa4fec')
        cls.p1_uuid3 = uuid.UUID('f69601d8-abf1-40dd-b7da-d8f072683b1f')
        cls.p2_uuid1 = uuid.UUID('b39e6293-6339-4ea3-b257-a31e776d46a4')
        cls.p2_uuid2 = uuid.UUID('f4cf6dc3-12e8-4811-a4ce-f5c80826818b')
        cls.p2_uuid3 = uuid.UUID('d7186c21-572c-4405-b05d-3280d476d001')

    def setUp(self):
        self.alert_instance1_p1 = self.make_alert_schedule_instance(self.p1_uuid1)
        save_alert_schedule_instance(self.alert_instance1_p1)

        self.alert_instance2_p2 = self.make_alert_schedule_instance(self.p2_uuid1, schedule_id=self.schedule_id1)
        save_alert_schedule_instance(self.alert_instance2_p2)

        self.alert_instance3_p1 = self.make_alert_schedule_instance(self.p1_uuid2, schedule_id=self.schedule_id1,
            active=False)
        save_alert_schedule_instance(self.alert_instance3_p1)

        self.timed_instance1_p2 = self.make_timed_schedule_instance(self.p2_uuid2)
        save_timed_schedule_instance(self.timed_instance1_p2)

        self.timed_instance2_p1 = self.make_timed_schedule_instance(self.p1_uuid3, schedule_id=self.schedule_id2)
        save_timed_schedule_instance(self.timed_instance2_p1)

        self.timed_instance3_p2 = self.make_timed_schedule_instance(self.p2_uuid3, schedule_id=self.schedule_id2,
            active=False)
        save_timed_schedule_instance(self.timed_instance3_p2)

    def tearDown(self):
        for db in partition_config.get_form_processing_dbs():
            AlertScheduleInstance.objects.using(db).filter(domain=self.domain).delete()
            TimedScheduleInstance.objects.using(db).filter(domain=self.domain).delete()

    def test_uuids_used(self):
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p1_uuid1), self.db1)
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p1_uuid2), self.db1)
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p1_uuid3), self.db1)
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p2_uuid1), self.db2)
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p2_uuid2), self.db2)
        self.assertEqual(ShardAccessor.get_database_for_doc(self.p2_uuid3), self.db2)

    def test_delete_alert_schedule_instance(self):
        self.assertEqual(AlertScheduleInstance.objects.using(self.db1).count(), 2)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db2).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db1).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db2).count(), 2)

        delete_alert_schedule_instance(self.alert_instance1_p1)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db1).count(), 1)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db2).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db1).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db2).count(), 2)

        with self.assertRaises(AlertScheduleInstance.DoesNotExist):
            get_alert_schedule_instance(self.p1_uuid1)

    def test_delete_timed_schedule_instance(self):
        self.assertEqual(AlertScheduleInstance.objects.using(self.db1).count(), 2)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db2).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db1).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db2).count(), 2)

        delete_timed_schedule_instance(self.timed_instance1_p2)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db1).count(), 2)
        self.assertEqual(AlertScheduleInstance.objects.using(self.db2).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db1).count(), 1)
        self.assertEqual(TimedScheduleInstance.objects.using(self.db2).count(), 1)

        with self.assertRaises(TimedScheduleInstance.DoesNotExist):
            get_timed_schedule_instance(self.p2_uuid2)

    def test_get_active_alert_schedule_instance_ids(self):
        self.assertItemsEqual(
            get_active_schedule_instance_ids(
                AlertScheduleInstance,
                datetime(2017, 4, 1),
                due_after=datetime(2017, 2, 1),
            ),
            [
                (self.domain, self.alert_instance1_p1.schedule_instance_id,
                    self.alert_instance1_p1.next_event_due),
                (self.domain, self.alert_instance2_p2.schedule_instance_id,
                    self.alert_instance2_p2.next_event_due),
            ]
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
            [
                (self.domain, self.timed_instance1_p2.schedule_instance_id,
                    self.timed_instance1_p2.next_event_due),
                (self.domain, self.timed_instance2_p1.schedule_instance_id,
                    self.timed_instance2_p1.next_event_due),
            ]
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
            [self.alert_instance2_p2, self.alert_instance3_p1]
        )

    def test_get_timed_schedule_instances_for_schedule(self):
        self.assertItemsEqual(
            get_timed_schedule_instances_for_schedule(TimedSchedule(schedule_id=self.schedule_id2)),
            [self.timed_instance2_p1, self.timed_instance3_p2]
        )
