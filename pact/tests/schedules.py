from django.test import TestCase
from pact.lib.quicksect import IntervalNode
from datetime import datetime, timedelta
from pact.models import PactPatientCase, CDotWeeklySchedule

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

class BasicCaseTests(TestCase):
    def setUp(self):
        pass

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
#            print "inserting week: %d" % counter
            counter = counter + 1

        td_hours = timedelta(hours=4)

        start_check = time_start
        check_time = time_start
        day_count = 0
        hour_count = 0
        self.node_hits = 0
        while check_time < time_end:
            def report_schedule(node):
                if node.other is not None:
                    self.node_hits += 1
            tree.intersect(check_time.toordinal(), check_time.toordinal(), report_schedule)
            check_time = check_time + td_hours
            if check_time > start_check+td_days:
                #print "node hits per interval: %d" % self.node_hits
                self.node_hits = 0
                start_check = check_time



    def testPatientSchedule(self):

        test_patient = PactPatientCase()
        test_patient.computed_ = {}

        test_patient.computed_[WEEKLY_SCHEDULE_KEY] = [CDotWeeklySchedule.wrap(x) for x in WEEKLY_SCHEDULE_EXAMPLES]


        #add a new schedule, verify tail is x-present, and [-2] is x-x

        new_schedule = None






        pass

