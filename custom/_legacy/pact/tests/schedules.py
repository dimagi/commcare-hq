import uuid
from django.test import TestCase, SimpleTestCase
from pact.lib.quicksect import IntervalNode
from datetime import datetime, timedelta
from pact.models import PactPatientCase, CDotWeeklySchedule
import pytz


utc = pytz.UTC

NEW_START_DATE = "2013-01-26T13:01:30Z"
NEW_SCHEDULE = {
    "comment": "",
    "doc_type": "CDotWeeklySchedule",
    "schedule_id": uuid.uuid4().hex,
    "edited_by": None,
    "monday": 'ctsims',
    "started": NEW_START_DATE,
    "deprecated": False,
    "tuesday": "ctsims",
    "friday": None,
    "wednesday": 'ctsims',
    "thursday": None,
    "ended": None,
    "sunday": None,
    "created_by": "cm326",
    "saturday": None
}


WEEKLY_SCHEDULE_KEY = 'pact_weekly_schedule'
WEEKLY_SCHEDULE_EXAMPLES = [
        {
            "comment": "",
            "doc_type": "CDotWeeklySchedule",
            "edited_by": None,
            "monday": "godfrey",
            "started": "2010-11-19T23:37:48Z",
            "deprecated": True,
            "_rev": "4-94fb80c843e86b4c04d8d2e88c286b6d",
            "friday": "godfrey",
            "wednesday": "godfrey",
            "created_by": "admin",
            "sunday": "godfrey",
            "ended": "2010-11-22T13:27:02Z",
            "schedule_id": "04b34f9cf43611df8f35005056977568",
            "thursday": "godfrey",
            "tuesday": "godfrey",
            "_id": "66a4f2d0e9d5467e34122514c36145f1",
            "saturday": "godfrey"
        },
        {
            "comment": "",
            "doc_type": "CDotWeeklySchedule",
            "edited_by": None,
            "monday": "cm326",
            "started": "2010-11-22T13:27:02Z",
            "deprecated": True,
            "_rev": "4-fb554c24b08a8bed69eb36cdbb14fdf5",
            "friday": "godfrey",
            "wednesday": "cm326",
            "created_by": "cm326",
            "sunday": None,
            "ended": "2011-01-05T15:45:01Z",
            "schedule_id": "30af0a20f63c11df8f35005056977568",
            "thursday": "cm326",
            "tuesday": "cm326",
            "_id": "55888063e298887dfe2ba223a03ef7d0",
            "saturday": None
        },
        {
            "comment": "",
            "doc_type": "CDotWeeklySchedule",
            "edited_by": None,
            "monday": None,
            "started": "2011-01-05T15:45:01Z",
            "deprecated": True,
            "_rev": "4-54e7f76747ae901526c9d1b5f4ea757e",
            "friday": "ctsims",
            "wednesday": None,
            "created_by": "cm326",
            "sunday": None,
            "ended": "2011-01-26T19:04:05Z",
            "schedule_id": "c213316218e211e08f35005056977568",
            "thursday": None,
            "tuesday": None,
            "_id": "55888063e298887dfe2ba223a0acc575",
            "saturday": None
        },
        {
            "comment": "testing missing submission flags",
            "doc_type": "CDotWeeklySchedule",
            "edited_by": None,
            "monday": None,
            "started": "2011-01-26T19:04:05Z",
            "deprecated": True,
            "_rev": "2-94839dae8e39173f30471b1c8a60a3dc",
            "friday": "cm326",
            "wednesday": "cm326",
            "created_by": "cm326",
            "sunday": "ctsims",
            "ended": "2011-02-25T14:05:32Z",
            "schedule_id": "0b72b8c6297f11e08f35005056977568",
            "thursday": "cm326",
            "tuesday": "cm326",
            "_id": "93bb5dd2590222718ee975c11322a502",
            "saturday": None
        },
        {
            "comment": "",
            "doc_type": "CDotWeeklySchedule",
            "schedule_id": "2481c602401f11e0af2e005056977568",
            "edited_by": None,
            "monday": None,
            "started": "2011-02-25T14:05:32Z",
            "deprecated": False,
            "tuesday": "ctsims",
            "friday": None,
            "wednesday": None,
            "thursday": None,
            "ended": None,
            "sunday": None,
            "created_by": "cm326",
            "saturday": None
        }
    ]


class SimpleScheduleTests(SimpleTestCase):

    def testSimpleIntervals(self):
        td_days = timedelta(days=7)
        time_start = datetime.utcnow() - timedelta(days=365)
        time_end = datetime.utcnow()

        tree = IntervalNode(time_start.toordinal(), time_end.toordinal())

        int_end = time_start + td_days
        int_start = time_start
        counter = 0
        while int_end < time_end:
            tree.insert(int_start.toordinal(), int_end.toordinal(), other="week %d" % counter)

            int_start = int_end
            int_end = int_end+td_days
            counter = counter + 1

        td_hours = timedelta(hours=4)

        start_check = time_start
        check_time = time_start
        self.node_hits = 0
        while check_time < time_end:
            def report_schedule(node):
                if node.other is not None:
                    self.node_hits += 1
            tree.intersect(check_time.toordinal(), check_time.toordinal(), report_schedule)
            check_time = check_time + td_hours
            if check_time > start_check+td_days:
                self.node_hits = 0
                start_check = check_time

    def testCreatePatientSchedule(self):
        """
        Single schedule create/remove
        """
        test_patient = PactPatientCase()
        test_patient.computed_ = {}
        test_patient.set_schedule(CDotWeeklySchedule.wrap(NEW_SCHEDULE))
        schedules = test_patient.get_schedules()

        self.assertEqual(len(schedules), 1)

        self.assertIsNone(schedules[0].ended)
        self.assertEquals(schedules[0].started.isoformat()[0:10], datetime.utcnow().isoformat()[0:10])
        self.assertTrue(schedules[0].is_current)
        test_patient.rm_last_schedule()
        updated_schedules = test_patient.get_schedules()

        self.assertEqual(len(updated_schedules), 0)


class ScheduleTests(TestCase):

    def testExtendingPatientSchedule(self):

        test_patient = PactPatientCase()
        test_patient.computed_ = {}

        # hand make it
        test_patient.computed_[WEEKLY_SCHEDULE_KEY] = WEEKLY_SCHEDULE_EXAMPLES

        # verify that tail is <date> - null
        api_schedules = test_patient.get_schedules(raw_json=True)
        self.assertIsNone(api_schedules[-1]['ended'])
        self.assertEquals(api_schedules[-1]['started'],
                          '2011-02-25T14:05:32Z')

        self.assertEquals(len(api_schedules), len(WEEKLY_SCHEDULE_EXAMPLES))

        # add a new schedule, verify tail is <date>-present, and [-2] is <datex> - <datey>

        test_patient.set_schedule(CDotWeeklySchedule.wrap(NEW_SCHEDULE))

        updated_schedules = test_patient.get_schedules(raw_json=True)
        self.assertIsNone(updated_schedules[-1]['ended'])
        self.assertEquals(len(updated_schedules), len(WEEKLY_SCHEDULE_EXAMPLES)+1)

        self.assertEquals(updated_schedules[-1]['started'][0:10], datetime.utcnow().isoformat()[0:10])

        self.assertIsNotNone(updated_schedules[-2]['ended'])
        self.assertLess(updated_schedules[-2]['ended'], datetime.utcnow().isoformat())

        # remove tail
        test_patient.save()
        loaded_patient = PactPatientCase.get(test_patient.get_id)

        loaded_patient.rm_last_schedule()

        removed_schedules = loaded_patient.get_schedules(raw_json=True)
        self.assertEquals(len(removed_schedules), len(WEEKLY_SCHEDULE_EXAMPLES))
        self.assertIsNone(removed_schedules[-1]['ended'])
        self.assertEquals(removed_schedules[-1]['started'],
                          '2011-02-25T14:05:32Z')
