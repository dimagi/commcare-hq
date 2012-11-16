from django.test import TestCase
from pact.lib.quicksect import IntervalNode
from datetime import datetime, timedelta


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
            print "inserting week: %d" % counter
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
                print "node hits per interval: %d" % self.node_hits
                self.node_hits = 0
                start_check = check_time

