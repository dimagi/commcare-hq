from __future__ import absolute_import
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.tests.utils import partitioned
from corehq.messaging.scheduling.scheduling_partitioned.dbaccessors import (
    save_alert_schedule_instance,
    save_timed_schedule_instance,
    delete_alert_schedule_instance,
    delete_timed_schedule_instance,
    get_alert_schedule_instances_for_schedule,
    get_timed_schedule_instances_for_schedule,
    delete_alert_schedule_instances_for_schedule,
    delete_timed_schedule_instances_for_schedule,
)
from corehq.messaging.scheduling.scheduling_partitioned.models import (
    AlertScheduleInstance,
    TimedScheduleInstance,
)
from corehq.messaging.scheduling.models import (
    AlertSchedule,
    TimedSchedule,
    TimedEvent,
    RandomTimedEvent,
    SMSContent,
)
from corehq.messaging.scheduling.tasks import (
    refresh_alert_schedule_instances,
    refresh_timed_schedule_instances,
)
from datetime import datetime, date, time
from django.test import TestCase
from mock import patch


class BaseScheduleTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(BaseScheduleTest, cls).setUpClass()
        cls.domain = 'scheduling-test'
        cls.domain_obj = Domain(name=cls.domain, default_timezone='America/New_York')
        cls.domain_obj.save()
        cls.user1 = CommCareUser.create(cls.domain, 'user1', 'password')
        cls.user2 = CommCareUser.create(cls.domain, 'user2', 'password')

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(BaseScheduleTest, cls).tearDownClass()

    def assertTimedScheduleInstance(self, instance, current_event_num, schedule_iteration_num,
            next_event_due, active, start_date, recipient):
        self.assertEqual(instance.domain, self.domain)
        self.assertEqual(instance.recipient_type, recipient.doc_type)
        self.assertEqual(instance.recipient_id, recipient.get_id)
        self.assertEqual(instance.timed_schedule_id, self.schedule.schedule_id)
        self.assertEqual(instance.current_event_num, current_event_num)
        self.assertEqual(instance.schedule_iteration_num, schedule_iteration_num)
        self.assertEqual(instance.next_event_due, next_event_due)
        self.assertEqual(instance.active, active)
        self.assertEqual(instance.start_date, start_date)

    def assertRandomTimedScheduleInstance(self, instance, current_event_num, schedule_iteration_num,
            next_event_due_min, next_event_due_max, active, start_date, recipient):
        self.assertEqual(instance.domain, self.domain)
        self.assertEqual(instance.recipient_type, recipient.doc_type)
        self.assertEqual(instance.recipient_id, recipient.get_id)
        self.assertEqual(instance.timed_schedule_id, self.schedule.schedule_id)
        self.assertEqual(instance.current_event_num, current_event_num)
        self.assertEqual(instance.schedule_iteration_num, schedule_iteration_num)
        self.assertGreaterEqual(instance.next_event_due, next_event_due_min)
        self.assertLessEqual(instance.next_event_due, next_event_due_max)
        self.assertEqual(instance.active, active)
        self.assertEqual(instance.start_date, start_date)

    def assertNumInstancesForSchedule(self, num):
        self.assertEqual(len(list(get_timed_schedule_instances_for_schedule(self.schedule))), num)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class TimedScheduleActiveFlagTest(BaseScheduleTest):

    def setUp(self):
        super(TimedScheduleActiveFlagTest, self).setUp()
        self.schedule = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(12, 0)),
            SMSContent(),
            total_iterations=2,
        )

    def tearDown(self):
        delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, self.schedule.schedule_id)
        self.schedule.delete()
        super(TimedScheduleActiveFlagTest, self).tearDown()

    def test_deactivate(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), True, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Deactivate
        self.schedule.active = False
        self.schedule.save()
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), False, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_activate_without_moving_to_next_event(self, utcnow_patch, send_patch):
        self.schedule.active = False
        self.schedule.save()

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), False, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Activate
        self.schedule.active = True
        self.schedule.save()
        utcnow_patch.return_value = datetime(2017, 3, 16, 7, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), True, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_activate_with_moving_to_next_event(self, utcnow_patch, send_patch):
        self.schedule.active = False
        self.schedule.save()

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), False, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Activate
        self.schedule.active = True
        self.schedule.save()
        utcnow_patch.return_value = datetime(2017, 3, 16, 17, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 2, datetime(2017, 3, 17, 16, 0), True, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_activate_when_total_iterations_are_done(self, utcnow_patch, send_patch):
        self.schedule.active = False
        self.schedule.save()

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), False, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Activate
        # On the first iteration, it tries to reactivate but the instance ends up moving
        # to the end of the schedule and being put into an inactive state as a result.
        # On the second iteration, it realizes the total iterations have been completed,
        # so nothing changes.
        self.schedule.active = True
        self.schedule.save()
        utcnow_patch.return_value = datetime(2017, 4, 1, 17, 0)
        for i in range(2):
            refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
                date(2017, 3, 16))
            self.assertNumInstancesForSchedule(1)
            [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
            self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 3, 18, 16, 0), False,
                date(2017, 3, 16), self.user1)
            self.assertEqual(send_patch.call_count, 0)


@partitioned
class DeleteScheduleInstancesTest(BaseScheduleTest):

    def setUp(self):
        super(DeleteScheduleInstancesTest, self).setUp()
        self.timed_schedule_1 = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(12, 0)),
            SMSContent(),
            total_iterations=1,
        )
        self.timed_schedule_2 = TimedSchedule.create_simple_daily_schedule(
            self.domain,
            TimedEvent(time=time(12, 0)),
            SMSContent(),
            total_iterations=1,
        )
        self.alert_schedule_1 = AlertSchedule.create_simple_alert(self.domain, SMSContent())
        self.alert_schedule_2 = AlertSchedule.create_simple_alert(self.domain, SMSContent())

    def tearDown(self):
        for schedule in (self.alert_schedule_1, self.alert_schedule_2):
            delete_alert_schedule_instances_for_schedule(AlertScheduleInstance, schedule.schedule_id)
            schedule.delete()

        for schedule in (self.timed_schedule_1, self.timed_schedule_2):
            delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, schedule.schedule_id)
            schedule.delete()

        super(DeleteScheduleInstancesTest, self).tearDown()

    @staticmethod
    def count(generator):
        return len(list(generator))

    def test_delete_alert_schedule_instances_for_schedule(self):
        refresh_alert_schedule_instances(
            self.alert_schedule_1.schedule_id,
            (('CommCareUser', self.user1.get_id),)
        )
        refresh_alert_schedule_instances(
            self.alert_schedule_2.schedule_id,
            (('CommCareUser', self.user1.get_id), ('CommCareUser', self.user2.get_id))
        )
        self.assertEqual(self.count(get_alert_schedule_instances_for_schedule(self.alert_schedule_1)), 1)
        self.assertEqual(self.count(get_alert_schedule_instances_for_schedule(self.alert_schedule_2)), 2)

        delete_alert_schedule_instances_for_schedule(AlertScheduleInstance, self.alert_schedule_2.schedule_id)
        self.assertEqual(self.count(get_alert_schedule_instances_for_schedule(self.alert_schedule_1)), 1)
        self.assertEqual(self.count(get_alert_schedule_instances_for_schedule(self.alert_schedule_2)), 0)

    def test_delete_timed_schedule_instances_for_schedule(self):
        refresh_timed_schedule_instances(
            self.timed_schedule_1.schedule_id,
            (('CommCareUser', self.user1.get_id),)
        )
        refresh_timed_schedule_instances(
            self.timed_schedule_2.schedule_id,
            (('CommCareUser', self.user1.get_id), ('CommCareUser', self.user2.get_id))
        )
        self.assertEqual(self.count(get_timed_schedule_instances_for_schedule(self.timed_schedule_1)), 1)
        self.assertEqual(self.count(get_timed_schedule_instances_for_schedule(self.timed_schedule_2)), 2)

        delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, self.timed_schedule_2.schedule_id)
        self.assertEqual(self.count(get_timed_schedule_instances_for_schedule(self.timed_schedule_1)), 1)
        self.assertEqual(self.count(get_timed_schedule_instances_for_schedule(self.timed_schedule_2)), 0)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class DailyScheduleTest(BaseScheduleTest):

    @classmethod
    def setUpClass(cls):
        super(DailyScheduleTest, cls).setUpClass()
        cls.schedule = TimedSchedule.create_simple_daily_schedule(
            cls.domain,
            TimedEvent(time=time(12, 0)),
            SMSContent(),
            total_iterations=2,
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        super(DailyScheduleTest, cls).tearDownClass()

    def tearDown(self):
        delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, self.schedule.schedule_id)
        super(DailyScheduleTest, self).tearDown()

    def test_schedule_start_to_finish(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), True, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Send first event
        utcnow_patch.return_value = datetime(2017, 3, 16, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 2, datetime(2017, 3, 17, 16, 0), True, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 1)

        # Send second (and final) event
        utcnow_patch.return_value = datetime(2017, 3, 17, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 3, 18, 16, 0), False, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 2)

    def test_recalculate_schedule(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), True, date(2017, 3, 16),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Set start date one day back
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 15))
        old_id = instance.schedule_instance_id
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertEqual(instance.schedule_instance_id, old_id)
        self.assertTimedScheduleInstance(instance, 0, 2, datetime(2017, 3, 16, 16, 0), True, date(2017, 3, 15),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Set start date one more day back
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 14))
        old_id = instance.schedule_instance_id
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertEqual(instance.schedule_instance_id, old_id)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 3, 16, 16, 0), False, date(2017, 3, 14),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_keep_in_sync_with_recipients(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance for user1
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), True, date(2017, 3, 16),
            self.user1)

        # Add user2
        refresh_timed_schedule_instances(self.schedule.schedule_id,
            (('CommCareUser', self.user1.get_id), ('CommCareUser', self.user2.get_id)), date(2017, 3, 16))

        self.assertNumInstancesForSchedule(2)
        [instance1, instance2] = get_timed_schedule_instances_for_schedule(self.schedule)
        if instance1.recipient_id == self.user1.get_id:
            user1_instance = instance1
            user2_instance = instance2
        else:
            user1_instance = instance2
            user2_instance = instance1

        self.assertTimedScheduleInstance(user1_instance, 0, 1, datetime(2017, 3, 16, 16, 0), True,
            date(2017, 3, 16), self.user1)
        self.assertTimedScheduleInstance(user2_instance, 0, 1, datetime(2017, 3, 16, 16, 0), True,
            date(2017, 3, 16), self.user2)

        # Remove user1
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user2.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0), True, date(2017, 3, 16),
            self.user2)

        self.assertEqual(send_patch.call_count, 0)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class RandomTimedEventTest(BaseScheduleTest):

    @classmethod
    def setUpClass(cls):
        super(RandomTimedEventTest, cls).setUpClass()
        cls.schedule = TimedSchedule.create_simple_daily_schedule(
            cls.domain,
            RandomTimedEvent(time=time(12, 0), window_length=120),
            SMSContent(),
            total_iterations=2,
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        super(RandomTimedEventTest, cls).tearDownClass()

    def tearDown(self):
        delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, self.schedule.schedule_id)
        super(RandomTimedEventTest, self).tearDown()

    def test_schedule_start_to_finish(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertRandomTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 16, 0),
            datetime(2017, 3, 16, 17, 59), True, date(2017, 3, 16), self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Send first event
        utcnow_patch.return_value = datetime(2017, 3, 16, 18, 0)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertRandomTimedScheduleInstance(instance, 0, 2, datetime(2017, 3, 17, 16, 0),
            datetime(2017, 3, 17, 17, 59), True, date(2017, 3, 16), self.user1)
        self.assertEqual(send_patch.call_count, 1)

        # Send second (and final) event
        utcnow_patch.return_value = datetime(2017, 3, 17, 18, 0)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertRandomTimedScheduleInstance(instance, 0, 3, datetime(2017, 3, 18, 16, 0),
            datetime(2017, 3, 18, 17, 59), False, date(2017, 3, 16), self.user1)
        self.assertEqual(send_patch.call_count, 2)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class RandomTimedEventSpanningTwoDaysTest(BaseScheduleTest):

    @classmethod
    def setUpClass(cls):
        super(RandomTimedEventSpanningTwoDaysTest, cls).setUpClass()
        cls.schedule = TimedSchedule.create_simple_daily_schedule(
            cls.domain,
            RandomTimedEvent(time=time(23, 0), window_length=120),
            SMSContent(),
            total_iterations=1,
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        super(RandomTimedEventSpanningTwoDaysTest, cls).tearDownClass()

    def tearDown(self):
        delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, self.schedule.schedule_id)
        super(RandomTimedEventSpanningTwoDaysTest, self).tearDown()

    def test_schedule(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 16))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertRandomTimedScheduleInstance(instance, 0, 1, datetime(2017, 3, 17, 3, 0),
            datetime(2017, 3, 17, 14, 59), True, date(2017, 3, 16), self.user1)
        self.assertEqual(send_patch.call_count, 0)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class StartDayOfWeekTest(BaseScheduleTest):

    @classmethod
    def setUpClass(cls):
        super(StartDayOfWeekTest, cls).setUpClass()
        cls.schedule = TimedSchedule.create_simple_daily_schedule(
            cls.domain,
            TimedEvent(time=time(12, 0)),
            SMSContent(),
            total_iterations=2,
            start_day_of_week=TimedSchedule.MONDAY,
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        super(StartDayOfWeekTest, cls).tearDownClass()

    def tearDown(self):
        delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, self.schedule.schedule_id)
        super(StartDayOfWeekTest, self).tearDown()

    def test_setting_first_event_for_next_monday(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance using "today's date" (a Wednesday) as a start date.
        # Based on the schedule we should start sending on the next Monday
        utcnow_patch.return_value = datetime(2017, 8, 9, 7, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 8, 14, 16, 0), True, date(2017, 8, 9),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_setting_first_event_using_explicit_start_date(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance using an explicit start date (a Thursday).
        # Based on the schedule we should start sending on the next Monday
        utcnow_patch.return_value = datetime(2017, 8, 2, 7, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 8, 3))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 8, 7, 16, 0), True, date(2017, 8, 3),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_setting_first_event_for_today_when_time_has_passed(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance using "today's date" (Monday) as the start date.
        # Since the time has already passed for today's event, we schedule it for next Monday.
        utcnow_patch.return_value = datetime(2017, 8, 7, 20, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 8, 14, 16, 0), True, date(2017, 8, 14),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_setting_first_event_for_today_when_time_has_not_yet_passed(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance using "today's date" (Monday) as the start date.
        # Since the time has not yet passed for today's event, we schedule it for today.
        utcnow_patch.return_value = datetime(2017, 8, 7, 7, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 8, 7, 16, 0), True, date(2017, 8, 7),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_setting_first_event_for_past_schedule(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance using an explicit start date in the past.
        # Since the date is so far back, the schedule is automatically deactivated.
        utcnow_patch.return_value = datetime(2017, 8, 9, 7, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 7, 1))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 7, 5, 16, 0), False, date(2017, 7, 1),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

    def test_schedule_start_to_finish(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 8, 6, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 8, 7, 16, 0), True, date(2017, 8, 6),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Send first event
        utcnow_patch.return_value = datetime(2017, 8, 7, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 2, datetime(2017, 8, 8, 16, 0), True, date(2017, 8, 6),
            self.user1)
        self.assertEqual(send_patch.call_count, 1)

        # Send second (and final) event
        utcnow_patch.return_value = datetime(2017, 8, 8, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 8, 9, 16, 0), False, date(2017, 8, 6),
            self.user1)
        self.assertEqual(send_patch.call_count, 2)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class StartDayOfWeekWithStartOffsetTest(BaseScheduleTest):

    @classmethod
    def setUpClass(cls):
        super(StartDayOfWeekWithStartOffsetTest, cls).setUpClass()
        cls.schedule = TimedSchedule.create_simple_daily_schedule(
            cls.domain,
            TimedEvent(time=time(12, 0)),
            SMSContent(),
            total_iterations=2,
            start_offset=3,
            start_day_of_week=TimedSchedule.MONDAY,
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        super(StartDayOfWeekWithStartOffsetTest, cls).tearDownClass()

    def tearDown(self):
        delete_timed_schedule_instances_for_schedule(TimedScheduleInstance, self.schedule.schedule_id)
        super(StartDayOfWeekWithStartOffsetTest, self).tearDown()

    def test_schedule_start_to_finish(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance using an explicit start date (a Sunday)
        # Based on the schedule (with start offset 3) we should start sending on the next Monday
        utcnow_patch.return_value = datetime(2017, 8, 2, 7, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 8, 6))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 8, 14, 16, 0), True, date(2017, 8, 6),
            self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Send first event
        utcnow_patch.return_value = datetime(2017, 8, 14, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 2, datetime(2017, 8, 15, 16, 0), True, date(2017, 8, 6),
            self.user1)
        self.assertEqual(send_patch.call_count, 1)

        # Send second (and final) event
        utcnow_patch.return_value = datetime(2017, 8, 15, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 8, 16, 16, 0), False, date(2017, 8, 6),
            self.user1)
        self.assertEqual(send_patch.call_count, 2)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class MonthlyScheduleTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(MonthlyScheduleTest, cls).setUpClass()
        cls.domain = 'scheduling-test'
        cls.domain_obj = Domain(name=cls.domain, default_timezone='America/New_York')
        cls.domain_obj.save()
        cls.user1 = CommCareUser.create(cls.domain, 'user1', 'password')
        cls.schedule = TimedSchedule.create_simple_monthly_schedule(
            cls.domain,
            TimedEvent(time=time(12, 0)),
            [1, 15],
            SMSContent(),
            total_iterations=2,
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        cls.domain_obj.delete()
        super(MonthlyScheduleTest, cls).tearDownClass()

    def tearDown(self):
        for instance in get_timed_schedule_instances_for_schedule(self.schedule):
            delete_timed_schedule_instance(instance)

    def assertTimedScheduleInstance(self, instance, current_event_num, schedule_iteration_num,
            next_event_due, active, start_date):
        self.assertEqual(instance.domain, self.domain)
        self.assertEqual(instance.recipient_type, self.user1.doc_type)
        self.assertEqual(instance.recipient_id, self.user1.get_id)
        self.assertEqual(instance.timed_schedule_id, self.schedule.schedule_id)
        self.assertEqual(instance.current_event_num, current_event_num)
        self.assertEqual(instance.schedule_iteration_num, schedule_iteration_num)
        self.assertEqual(instance.next_event_due, next_event_due)
        self.assertEqual(instance.active, active)
        self.assertEqual(instance.start_date, start_date)

    def assertNumInstancesForSchedule(self, num):
        self.assertEqual(len(list(get_timed_schedule_instances_for_schedule(self.schedule))), num)

    def test_schedule_start_to_finish(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 4, 1, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 4, 1))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 4, 1, 16, 0), True, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 0)

        # Send first event
        utcnow_patch.return_value = datetime(2017, 4, 1, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 1, 1, datetime(2017, 4, 15, 16, 0), True, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 1)

        # Send second event
        utcnow_patch.return_value = datetime(2017, 4, 15, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 2, datetime(2017, 5, 1, 16, 0), True, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 2)

        # Send third event
        utcnow_patch.return_value = datetime(2017, 5, 1, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 1, 2, datetime(2017, 5, 15, 16, 0), True, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 3)

        # Send fourth (and final) event
        utcnow_patch.return_value = datetime(2017, 5, 15, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 6, 1, 16, 0), False, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 4)

    def test_recalculate_schedule(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 4, 15, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 4, 15))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 1, 1, datetime(2017, 4, 15, 16, 0), True, date(2017, 4, 15))
        self.assertEqual(send_patch.call_count, 0)

        # Set start date in previous month
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 3, 14))
        old_id = instance.schedule_instance_id
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertEqual(instance.schedule_instance_id, old_id)
        self.assertTimedScheduleInstance(instance, 1, 2, datetime(2017, 4, 15, 16, 0), True, date(2017, 3, 14))
        self.assertEqual(send_patch.call_count, 0)

        # Set start date two months back
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 2, 1))
        old_id = instance.schedule_instance_id
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertEqual(instance.schedule_instance_id, old_id)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 4, 1, 16, 0), False, date(2017, 2, 1))
        self.assertEqual(send_patch.call_count, 0)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class EndOfMonthScheduleTest(TestCase):

    @classmethod
    def setUpClass(cls):
        super(EndOfMonthScheduleTest, cls).setUpClass()
        cls.domain = 'scheduling-test'
        cls.domain_obj = Domain(name=cls.domain, default_timezone='America/New_York')
        cls.domain_obj.save()
        cls.user1 = CommCareUser.create(cls.domain, 'user1', 'password')
        cls.schedule = TimedSchedule.create_simple_monthly_schedule(
            cls.domain,
            TimedEvent(time=time(12, 0)),
            [-1],
            SMSContent(),
            total_iterations=2,
        )

    @classmethod
    def tearDownClass(cls):
        cls.schedule.delete()
        cls.domain_obj.delete()
        super(EndOfMonthScheduleTest, cls).tearDownClass()

    def tearDown(self):
        for instance in get_timed_schedule_instances_for_schedule(self.schedule):
            delete_timed_schedule_instance(instance)

    def assertTimedScheduleInstance(self, instance, current_event_num, schedule_iteration_num,
            next_event_due, active, start_date):
        self.assertEqual(instance.domain, self.domain)
        self.assertEqual(instance.recipient_type, self.user1.doc_type)
        self.assertEqual(instance.recipient_id, self.user1.get_id)
        self.assertEqual(instance.timed_schedule_id, self.schedule.schedule_id)
        self.assertEqual(instance.current_event_num, current_event_num)
        self.assertEqual(instance.schedule_iteration_num, schedule_iteration_num)
        self.assertEqual(instance.next_event_due, next_event_due)
        self.assertEqual(instance.active, active)
        self.assertEqual(instance.start_date, start_date)

    def assertNumInstancesForSchedule(self, num):
        self.assertEqual(len(list(get_timed_schedule_instances_for_schedule(self.schedule))), num)

    def test_schedule_start_to_finish(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the instance
        utcnow_patch.return_value = datetime(2017, 4, 1, 6, 0)
        refresh_timed_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),),
            date(2017, 4, 1))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_timed_schedule_instances_for_schedule(self.schedule)
        self.assertTimedScheduleInstance(instance, 0, 1, datetime(2017, 4, 30, 16, 0), True, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 0)

        # Send first event
        utcnow_patch.return_value = datetime(2017, 4, 30, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 2, datetime(2017, 5, 31, 16, 0), True, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 1)

        # Send second (and final) event
        utcnow_patch.return_value = datetime(2017, 5, 31, 16, 1)
        instance.handle_current_event()
        save_timed_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertTimedScheduleInstance(instance, 0, 3, datetime(2017, 6, 30, 16, 0), False, date(2017, 4, 1))
        self.assertEqual(send_patch.call_count, 2)


@partitioned
@patch('corehq.messaging.scheduling.models.content.SMSContent.send')
@patch('corehq.messaging.scheduling.util.utcnow')
class AlertTest(TestCase):

    def setUp(self):
        super(AlertTest, self).setUp()
        self.domain = 'alert-test'
        self.domain_obj = Domain(name=self.domain, default_timezone='America/New_York')
        self.domain_obj.save()
        self.user1 = CommCareUser.create(self.domain, 'user1', 'password')
        self.user2 = CommCareUser.create(self.domain, 'user2', 'password')
        self.schedule = AlertSchedule.create_simple_alert(self.domain, SMSContent())

    def tearDown(self):
        delete_alert_schedule_instances_for_schedule(AlertScheduleInstance, self.schedule.schedule_id)
        self.schedule.delete()
        self.domain_obj.delete()
        super(AlertTest, self).tearDown()

    def assertAlertScheduleInstance(self, instance, current_event_num, schedule_iteration_num,
            next_event_due, active, recipient):
        self.assertEqual(instance.domain, self.domain)
        self.assertEqual(instance.recipient_type, recipient.doc_type)
        self.assertEqual(instance.recipient_id, recipient.get_id)
        self.assertEqual(instance.alert_schedule_id, self.schedule.schedule_id)
        self.assertEqual(instance.current_event_num, current_event_num)
        self.assertEqual(instance.schedule_iteration_num, schedule_iteration_num)
        self.assertEqual(instance.next_event_due, next_event_due)
        self.assertEqual(instance.active, active)

    def assertNumInstancesForSchedule(self, num):
        self.assertEqual(len(list(get_alert_schedule_instances_for_schedule(self.schedule))), num)

    def test_alert(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the alert
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 42, 21)
        refresh_alert_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_alert_schedule_instances_for_schedule(self.schedule)
        self.assertAlertScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 6, 42, 21), True, self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Send first event
        instance.handle_current_event()
        save_alert_schedule_instance(instance)
        self.assertNumInstancesForSchedule(1)
        self.assertAlertScheduleInstance(instance, 0, 2, datetime(2017, 3, 16, 6, 42, 21), False, self.user1)
        self.assertEqual(send_patch.call_count, 1)

        # Test copying of the alert schedule instance for a new recipient
        refresh_alert_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user2.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_alert_schedule_instances_for_schedule(self.schedule)
        self.assertAlertScheduleInstance(instance, 0, 2, datetime(2017, 3, 16, 6, 42, 21), False, self.user2)
        self.assertEqual(send_patch.call_count, 1)

    def test_inactive_schedule(self, utcnow_patch, send_patch):
        self.schedule.active = False
        self.schedule.save()
        self.assertNumInstancesForSchedule(0)

        # Scheduling the alert creates an inactive schedule instance
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 42, 21)
        refresh_alert_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_alert_schedule_instances_for_schedule(self.schedule)
        self.assertAlertScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 6, 42, 21), False, self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Reactivating later still results in an inactive instance because the time has now passed
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 42, 22)
        self.schedule.active = True
        self.schedule.save()

        for i in range(2):
            # On the first iteration, it tries to reactivate but the instance ends up moving
            # to the next event and being put into an inactive state as a result.
            # On the second iteration, it realizes the total iterations have been completed,
            # so nothing changes.
            refresh_alert_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
            self.assertNumInstancesForSchedule(1)
            [instance] = get_alert_schedule_instances_for_schedule(self.schedule)
            self.assertAlertScheduleInstance(instance, 0, 2, datetime(2017, 3, 16, 6, 42, 21), False, self.user1)
            self.assertEqual(send_patch.call_count, 0)

    def test_deactivating_schedule(self, utcnow_patch, send_patch):
        self.assertNumInstancesForSchedule(0)

        # Schedule the alert
        utcnow_patch.return_value = datetime(2017, 3, 16, 6, 42, 21)
        refresh_alert_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_alert_schedule_instances_for_schedule(self.schedule)
        self.assertAlertScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 6, 42, 21), True, self.user1)
        self.assertEqual(send_patch.call_count, 0)

        # Deactivate
        self.schedule.active = False
        self.schedule.save()
        refresh_alert_schedule_instances(self.schedule.schedule_id, (('CommCareUser', self.user1.get_id),))
        self.assertNumInstancesForSchedule(1)
        [instance] = get_alert_schedule_instances_for_schedule(self.schedule)
        self.assertAlertScheduleInstance(instance, 0, 1, datetime(2017, 3, 16, 6, 42, 21), False, self.user1)
        self.assertEqual(send_patch.call_count, 0)
