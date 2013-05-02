from datetime import datetime
from django import test as unittest
from django.test.client import RequestFactory
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser
from dimagi.utils.dates import DateSpan

from .sql_fixture import load_data
from .sql_reports import test_report, UserTestReport, RegionTestReport

DOMAIN = "test"
format_string = "%Y-%m-%d"


class BaseReportTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        load_data()

        create_domain(DOMAIN)
        cls.couch_user = WebUser.create(None, "report_test", "foobar")
        cls.couch_user.add_domain_membership(DOMAIN, is_admin=True)
        cls.couch_user.save()

        cls.factory = RequestFactory()

    def _get_report_data(self, report, startdate, enddate):
        req = self._get_request(startdate, enddate)
        rep = report(req, in_testing=True)
        return rep.json_dict['aaData']

    def _get_request(self, startdate, enddate):
        request = self.factory.get('/')
        request.couch_user = self.couch_user
        request.datespan = DateSpan(self.date(startdate), self.date(enddate), format_string)
        return request

    def date(self, d):
        return datetime.strptime(d, format_string)


class SimpleReportTest(BaseReportTest):
    def test_no_group_no_filter(self):
        data = self._get_report_data(test_report(UserTestReport), "2013-01-01", "2013-02-01")
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], [2, 2, 66])

    def test_no_group_with_filter(self):
        filters = ["date > :startdate"]
        report = test_report(UserTestReport, filters=filters)
        data = self._get_report_data(report, "2013-01-01", "2013-02-01")
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0], [1, 1, 66])

    def test_with_group_no_filter(self):
        keys = [["user1"], ["user2"]]  # specify keys to guarantee ordering
        report = test_report(UserTestReport, keys=keys, group_by=['user'])
        data = self._get_report_data(report, "2013-01-01", "2013-02-01")
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0], ['Joe', 1, 1, 100])
        self.assertEqual(data[1], ['Bob', 1, 1, 50])

    def test_with_group_with_filter(self):
        keys = [["user1"], ["user2"]]  # specify keys to guarantee ordering
        filters = ["date > :startdate"]
        report = test_report(UserTestReport, keys=keys, filters=filters, group_by=['user'])
        data = self._get_report_data(report, "2013-01-01", "2013-02-01")
        self.assertEqual(len(data), 2)
        self.assertEqual(data[0], ['Joe', 0, 1, 100])
        self.assertEqual(data[1], ['Bob', 1, 0, 50])

    def test_extra_keys(self):
        keys = [["user1"], ["user2"], ["user3"]]
        report = test_report(UserTestReport, keys=keys, group_by=['user'])
        data = self._get_report_data(report, "2013-01-01", "2013-02-01")
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0], ['Joe', 1, 1, 100])
        self.assertEqual(data[1], ['Bob', 1, 1, 50])
        self.assertEqual(data[2], ['Gill', '--', '--', '--'])

    def test_multi_level_grouping(self):
        keys = [
            ["region1", "region1_a"], ["region1", "region1_b"],
            ["region2", "region2_a"], ["region2", "region2_b"]
        ]
        report = test_report(RegionTestReport, keys=keys, group_by=["region", "sub_region"])
        data = self._get_report_data(report, "2013-01-01", "2013-02-01")
        self.assertEqual(len(data), 4)
        self.assertEqual(data[0], ['Cape Town', 'Ronderbosch', 2, 1])
        self.assertEqual(data[1], ['Cape Town', 'Newlands', 0, 1])
        self.assertEqual(data[2], ['Durban', 'Glenwood', 1, 2])
        self.assertEqual(data[3], ['Durban', 'Morningside', 1, 0])