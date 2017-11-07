from __future__ import absolute_import
import datetime
import uuid

import pytz
from django.test import override_settings, TestCase, RequestFactory
from mock import MagicMock

from corehq.form_processor.tests.utils import FormProcessorTestUtils
from custom.enikshay.const import ENIKSHAY_TIMEZONE
from custom.enikshay.reports import HistoricalAdherenceReport
from custom.enikshay.tests.utils import ENikshayCaseStructureMixin


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class HistoricalAdherenceReportTests(ENikshayCaseStructureMixin, TestCase):

    domain = "historical-adherence-test-domain"

    @classmethod
    def setUpClass(cls):
        super(HistoricalAdherenceReportTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases()

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases()

    def test_unobserved_dots_dose_image(self):
        # An unobserved dose was recorded in 99DOTS

        # Create Person, Occurrence, and Episode Cases.
        self.create_case_structure()

        # Create an adherence case
        date = datetime.date(2017, 1, 1)
        self.create_adherence_case(date, "99DOTS", adherence_value="unobserved_dose")

        self.assert_icon(date, "unobserved_dose_dot")

    def test_unobserved_dose_image(self):
        # An unobserved dose was recorded

        # Create Person, Occurrence, and Episode Cases.
        self.create_case_structure()

        # Create an adherence case
        date = datetime.date(2017, 1, 1)
        self.create_adherence_case(date, "enikshay", adherence_value="unobserved_dose")

        self.assert_icon(date, "unobserved_dose")

    def test_self_administered_dose_image(self):
        # Create Person, Occurrence, and Episode Cases.
        self.create_case_structure()

        # Create an adherence case
        date = datetime.date(2017, 1, 1)
        self.create_adherence_case(date, "enikshay", adherence_value="self_administered_dose")

        self.assert_icon(date, "self_administered_dose")

    def test_missed_dose_image(self):
        # Create Person, Occurrence, and Episode Cases.
        self.create_case_structure()

        # Create an adherence case
        date = datetime.date(2017, 1, 1)
        self.create_adherence_case(date, "enikshay", adherence_value="missed_dose")

        self.assert_icon(date, "missed_dose")

    def test_dose_unknown_expected_image(self):
        # There was no dose recorded for a day on which we expected one
        self.episode.attrs['update']["adherence_schedule_id"] = "schedule_mwf"
        self.episode.attrs['update']["adherence_schedule_date_start"] = datetime.date(2016, 1, 1)
        self.create_case_structure()
        date = datetime.date(2017, 1, 2)  # A monday
        self.assert_icon(date, "dose_unknown_expected")

    def test_directly_observed_dose_image(self):
        # Create Person, Occurrence, and Episode Cases.
        self.create_case_structure()

        # Create an adherence case
        date = datetime.date(2017, 1, 1)
        self.create_adherence_case(date, "enikshay", adherence_value="directly_observed_dose")

        self.assert_icon(date, "directly_observed_dose")

    def _get_report(self):
        # Create a request and report
        request = RequestFactory().get(
            "/a/{}/reports/custom/historical_adherence/?episode_id={}".format(self.domain, self.episode_id)
        )
        request.couch_user = MagicMock()
        request.datespan = MagicMock()
        return HistoricalAdherenceReport(request, domain=self.domain)

    def assert_icon(self, date, icon):
        report = self._get_report()

        # Get the image for the given day
        cases_dict = report.get_adherence_cases_dict()
        self.assertEqual(
            report.get_adherence_image_key(cases_dict[date], date),
            icon
        )

    def test_multiple_adherence_cases_for_same_day(self):

        # Create Person, Occurrence, and Episode Cases.
        self.create_case_structure()

        # Create an adherence case
        date = datetime.date(2017, 1, 1)
        self.create_adherence_case(
            date, "99DOTS", adherence_value="directly_observed_dose", case_id=uuid.uuid4().hex)
        self.create_adherence_case(
            date, "enikshay", adherence_value="self_administered_dose", case_id=uuid.uuid4().hex)
        self.create_adherence_case(
            date, "enikshay", adherence_value="unobserved_dose", case_id=uuid.uuid4().hex)
        self.create_adherence_case(
            date, "99DOTS", adherence_value="missed_dose", case_id=uuid.uuid4().hex)

        # All enikshay cases take priority over all 99DOTS cases
        # newer cases take priority over older cases
        self.assert_icon(date, "unobserved_dose")

    def test_default_datespan(self):
        date = datetime.date(2000, 1, 1)
        self.episode.attrs['update']['adherence_schedule_date_start'] = date
        self.create_case_structure()
        report = self._get_report()
        self.assertEqual(report.default_datespan.startdate, date)

        utc_now = datetime.datetime.now(pytz.utc)
        india_now = utc_now.astimezone(pytz.timezone(ENIKSHAY_TIMEZONE))

        self.assertEqual(report.default_datespan.enddate, india_now.date())

    def test_show_unexpected_image(self):
        # There was a dose recorded for a day on which we didn't expect one
        self.episode.attrs['update']["adherence_schedule_id"] = "schedule_mwf"
        self.episode.attrs['update']["adherence_schedule_date_start"] = datetime.date(2016, 1, 1)
        self.create_case_structure()
        date = datetime.date(2017, 1, 3)  # A Tuesday

        self.create_adherence_case(date, "enikshay", adherence_value="directly_observed_dose")

        report = self._get_report()
        cases_dict = report.get_adherence_cases_dict()
        self.assertTrue(
            report.show_unexpected_image(cases_dict[date], date),
        )

    def test_run_report(self):
        self.create_case_structure()
        date = datetime.date(2017, 1, 3)  # A Tuesday

        self.create_adherence_case(date, "enikshay", adherence_value="directly_observed_dose")

        report = self._get_report()
        context = report.report_context
        self.assertEqual(context['patient_name'], self.person.attrs['update']['name'])
        self.assertEqual(context['treatment_phase'], "IP")
        self.assertEqual(context['doses'], 1)
        self.assertEqual(context['adherence_schedule'], 'Daily')
        self.assertEqual(context['patient_type'], 'Treatment after loss to follow up (LFU)')
