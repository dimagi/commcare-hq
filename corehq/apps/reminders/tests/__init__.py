from datetime import datetime, timedelta
from django.test.testcases import TestCase
from casexml.apps.case.models import CommCareCase
from corehq.apps.reminders.models import CaseReminderHandler, Message
from corehq.apps.users.models import CouchUser, CommCareUser

class ReminderTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.domain = "test"
        cls.case_type = "my_case_type"
        cls.message = "Hey you're getting this message."
        cls.handler = CaseReminderHandler(
            domain=cls.domain,
            case_type=cls.case_type,
            method="test",
            start='start_sending',
            start_offset=1,
            frequency=3,
            until='stop_sending',
            message={'en': cls.message},
            default_lang='en',
        )
        cls.handler.save()
        cls.user_id = "USER-ID-109347"
        CommCareUser.create(cls.domain, 'chw.bob', '****', uuid=cls.user_id)


    def test_ok(self):
        self.assertEqual(self.handler.message['en'], self.message)

        case = CommCareCase(
            domain=self.domain,
            type=self.case_type,
            user_id=self.user_id,
        )
        case.save()
        self.assertEqual(self.handler.get_reminder(case), None)

        # create reminder
        CaseReminderHandler.now = datetime(year=2011, month=7, day=7, hour=19, minute=8)
        case.set_case_property('start_sending', 'ok')
        case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(
            reminder.next_fire,
            CaseReminderHandler.now + timedelta(days=self.handler.start_offset)
        )
        self.assertEqual(reminder.last_fired, None)

        # fire a day after created
        CaseReminderHandler.now = datetime(year=2011, month=7, day=8, hour=19, minute=8)
        case.set_case_property('irrelevant_1', 'ok')
        case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(
            reminder.next_fire,
            CaseReminderHandler.now + timedelta(days=self.handler.frequency)
        )
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

        # Shouldn't fire until three days after created
        last_fired = CaseReminderHandler.now
        CaseReminderHandler.now = datetime(year=2011, month=7, day=9, hour=19, minute=8)
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(reminder.last_fired, last_fired)
        self.assertEqual(
            reminder.next_fire,
            last_fired + timedelta(days=self.handler.frequency)
        )

        # fire three days after last fired
        CaseReminderHandler.now = datetime(year=2011, month=7, day=11, hour=19, minute=8)
        case.set_case_property('irrelevant_2', 'ok')
        case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(case)
        self.assertNotEqual(reminder, None)
        self.assertEqual(
            reminder.next_fire,
            CaseReminderHandler.now + timedelta(days=self.handler.frequency)
        )
        self.assertEqual(reminder.last_fired, CaseReminderHandler.now)

        # set stop_sending to 'ok' should make it stop sending and make the reminder inactive
        CaseReminderHandler.now = datetime(year=2011, month=7, day=14, hour=19, minute=8)
        case.set_case_property('stop_sending', 'ok')
        case.save()
        CaseReminderHandler.fire_reminders()
        reminder = self.handler.get_reminder(case)
        self.assertNotEqual(reminder, None)

    @classmethod
    def tearDownClass(cls):
        cls.handler.delete()

class MessageTestCase(TestCase):
    def test_message(self):
        message = 'The EDD for client with ID {case.external_id} is approaching in {case.edd.days_until} days.'
        case = {'external_id': 123, 'edd': datetime.utcnow() + timedelta(days=30)}
        outcome = 'The EDD for client with ID 123 is approaching in 30 days.'
        self.assertEqual(Message.render(message, case=case), outcome)