from __future__ import absolute_import
from builtins import range
from collections import defaultdict, namedtuple
import datetime

import pytz
from dateutil.parser import parse

from corehq.apps.locations.permissions import (
    location_safe,
    user_can_access_location_id,
    location_restricted_exception,
)
from corehq.apps.reports.datatables import DataTablesHeader
from corehq.apps.reports.exceptions import BadRequestError
from corehq.apps.reports.filters.base import BaseReportFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.const import SERVER_DATE_FORMAT
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.exceptions import CaseNotFound
from corehq.util.soft_assert import soft_assert
from custom.enikshay.case_utils import get_person_case_from_episode, get_adherence_cases_by_day
from custom.enikshay.const import DOSE_TAKEN_INDICATORS, ENIKSHAY_TIMEZONE, TREATMENT_START_DATE
from custom.enikshay.reports.generic import EnikshayReport

from django.utils.translation import ugettext_lazy

from custom.enikshay.tasks import EpisodeAdherenceUpdate, calculate_dose_status_by_day
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
import six

Schedule = namedtuple("Schedule", ['days_dose_expected', 'mark_expected', 'title'])
india_timezone = pytz.timezone(ENIKSHAY_TIMEZONE)


class HiddenFilter(BaseReportFilter):
    """A filter that is not displayed in the UI."""
    template = "reports/filters/hidden.html"
    slug = "hidden"
    label = "hidden"

    @property
    def filter_context(self):
        return {
            'value': self.get_value(self.request, self.domain),
        }


class EpisodeFilter(HiddenFilter):
    label = ugettext_lazy("Episode Case ID")
    slug = "episode_id"


@location_safe
class HistoricalAdherenceReport(EnikshayReport):

    name = ugettext_lazy('Historical Adherence')
    report_title = ugettext_lazy('Historical Adherence')
    slug = 'historical_adherence'
    use_datatables = False
    report_template_path = 'enikshay/historical_adherence.html'
    print_override_template = "enikshay/print_report.html"
    fields = (DatespanFilter, EpisodeFilter)

    emailable = False
    exportable = False
    printable = True

    def __init__(self, *args, **kwargs):
        super(HistoricalAdherenceReport, self).__init__(*args, **kwargs)
        try:
            self.episode = CaseAccessors(self.domain).get_case(self.episode_case_id)
        except CaseNotFound:
            raise BadRequestError()
        self.episode_properties = self.episode.dynamic_case_properties()
        self.person = get_person_case_from_episode(self.domain, self.episode_case_id)

    @classmethod
    def show_in_navigation(cls, domain=None, project=None, user=None):
        return False

    @classmethod
    def show_in_user_roles(cls, domain=None, project=None, user=None):
        return True

    @property
    def episode_case_id(self):
        return self.request.GET.get("episode_id")

    def decorator_dispatcher(self, request, *args, **kwargs):
        response = super(HistoricalAdherenceReport, self).decorator_dispatcher(request, *args, **kwargs)
        if not user_can_access_location_id(self.domain, self.request.couch_user, self.person.owner_id):
            raise location_restricted_exception(request)
        return response

    @property
    def headers(self):
        return DataTablesHeader()

    @property
    def rows(self):
        return []

    @property
    def default_datespan(self):
        start = self.adherence_schedule_date_start

        utc_now = datetime.datetime.now(pytz.utc)
        india_now = utc_now.astimezone(india_timezone)
        end = india_now.date()

        datespan = DateSpan(start, end, timezone=india_timezone, inclusive=self.inclusive)
        datespan.max_days = self.datespan_max_days
        datespan.is_default = True

        return datespan

    @property
    def report_context(self):
        report_context = super(HistoricalAdherenceReport, self).report_context

        report_context['weeks'] = self.get_calendar()
        report_context['patient_name'] = self.person.name
        report_context['treatment_phase'] = self.get_treatment_phase()
        report_context['doses'] = self.get_doses()
        report_context['adherence_schedule'] = self.get_adherence_schedule().title
        report_context['patient_type'] = self.get_patient_type()

        return report_context

    def get_doses(self):
        adherence_cases = []
        for day, cases in six.iteritems(self.get_adherence_cases_dict()):
            adherence_cases.extend(cases)

        doses_taken_by_date = calculate_dose_status_by_day(
            [c.to_json() for c in adherence_cases]
        )
        return EpisodeAdherenceUpdate.count_doses_taken(doses_taken_by_date)

    def get_treatment_phase(self):
        if self.episode_properties.get("treatment_initiated", False) in ("yes_phi", "yes_private"):
            if self.episode_properties.get("cp_initiated", False) == "yes":
                return "CP"
            return "IP"
        return ""

    def get_patient_type(self):
        type_ = self.episode_properties.get("patient_type_choice", None)
        return {
            "new": "New",
            "recurrent": "Recurrent",
            "treatment_after_failure": "Treatment after failure",
            "treatment_after_lfu": "Treatment after loss to follow up (LFU)",
            "other_previously_treated": "Other previously treated",
        }.get(type_, None)

    def get_adherence_schedule(self):
        schedule_id = self.episode_properties.get("adherence_schedule_id", "schedule_daily")
        # Note: This configuration is stored in the "adherence_schedules" fixture, but reproducing it here to avoid
        # extra db lookups, and because this information should be pretty static.
        return {
            # 0 is monday
            "schedule_daily": Schedule([0, 1, 2, 3, 4, 5, 6], False, 'Daily'),
            "schedule_trs": Schedule([1, 3, 5], True, 'Intermittent (TTS)'),
            "schedule_mwf": Schedule([0, 2, 4], True, 'Intermittent (MWF)'),
        }[schedule_id]

    @property
    def mark_expected(self):
        return self.get_adherence_schedule().mark_expected

    @property
    def expected_days(self):
        return self.get_adherence_schedule().days_dose_expected

    @property
    def adherence_schedule_date_start(self):
        day = self.episode_properties.get('adherence_schedule_date_start')
        if not day:
            day = self.episode_properties.get(TREATMENT_START_DATE)
        return parse(day).date()

    @memoized
    def get_adherence_cases_dict(self):
        return get_adherence_cases_by_day(self.domain, self.episode_case_id)

    def _get_first_sunday_before_or_equal_to(self, date):
        day = datetime.date(date.year, date.month, date.day)
        while day.weekday() != 6:  # 6 is sunday
            day -= datetime.timedelta(days=1)
        return day

    def get_calendar(self):
        """
        Return a list of Week objects
        """
        adherence_cases_dict = self.get_adherence_cases_dict()
        first_date, last_date = self._get_date_range()
        assert first_date <= last_date

        calendar = []  # A list of Weeks
        sunday = self._get_first_sunday_before_or_equal_to(first_date)
        while sunday <= self._get_first_sunday_before_or_equal_to(last_date):
            days = []
            for i in range(7):
                date = sunday + datetime.timedelta(days=i)
                if date >= first_date and date <= last_date:
                    cases_for_date = adherence_cases_dict.get(date, [])
                    days.append(Day(
                        date,
                        self.get_adherence_image_key(cases_for_date, date),
                        self.show_unexpected_image(cases_for_date, date),
                        len(cases_for_date) > 1,
                        self.is_treatment_start_date(date),
                        force_month_label=date == first_date,
                    ))
                else:
                    # The day won't be rendered on the screen, but a placeholder will appear
                    days.append(None)
            calendar.append(Week(days))
            sunday += datetime.timedelta(days=7)

        return calendar

    def _get_date_range(self):
        first_date = self.datespan.startdate
        last_date = self.datespan.enddate

        # Sometimes the report dispatcher sets the request.datespan dates to be datetimes :(
        try:
            first_date = first_date.date()
        except AttributeError:
            pass
        try:
            last_date = last_date.date()
        except AttributeError:
            pass

        return first_date, last_date

    def get_primary_adherence_case(self, adherence_cases):
        """
        Return the case who's adherence value should be used.
        Cases with adherence_source == enikshay take precedence over other sources
        Then open cases tak precedence over other cases
        Then cases with a later modified_on take precedence over earlier cases
        Then cases with a later opened_on take precedence over earlier cases
        """
        if not adherence_cases:
            return None

        def _source_is_enikshay(case):
            return case.dynamic_case_properties().get('adherence_source') in ('enikshay', '')

        return sorted(
            adherence_cases, key=lambda c: (_source_is_enikshay(c), not c.closed, c.modified_on, c.opened_on)
        )[-1]

    def get_adherence_value(self, primary_adherence_case):
        if not primary_adherence_case:
            return None
        return primary_adherence_case.dynamic_case_properties().get('adherence_value')

    def get_adherence_source(self, primary_adherence_case):
        if not primary_adherence_case:
            return None
        return primary_adherence_case.dynamic_case_properties().get('adherence_source')

    def get_adherence_image_key(self, adherence_cases, date):
        primary_adherence_case = self.get_primary_adherence_case(adherence_cases)
        adherence_value = self.get_adherence_value(primary_adherence_case)
        if len(adherence_cases) == 0 or adherence_value == "missing_data":
            return self.unknown_img_holder(date)
        if adherence_value == "unobserved_dose":
            if self.get_adherence_source(primary_adherence_case) == "99DOTS":
                return "unobserved_dose_dot"
            return "unobserved_dose"
        if adherence_value not in (
            "dose_unknown_expected",
            "unobserved_dose_dot",
            "self_administered_dose",
            "unobserved_dose",
            "missed_dose",
            "directly_observed_dose",
            None,
            ""
        ):
            assert_ = soft_assert(to="{}@dimagi.com".format("cellowitz"))
            assert_(False, "Got an unexpected adherence_value of {} for case {}".format(
                adherence_value, primary_adherence_case.case_id))
        return adherence_value

    def unknown_img_holder(self, date):
        if (
            self.mark_expected
            and self.adherence_schedule_date_start < date
            and date.weekday() in self.expected_days
        ):
            return "dose_unknown_expected"

    def show_unexpected_image(self, adherence_cases, date):
        adherence_value = self.get_adherence_value(self.get_primary_adherence_case(adherence_cases))
        return (
            (self.mark_expected and self.adherence_schedule_date_start < date)
            and len(adherence_cases) > 0
            and adherence_value not in ("missed_dose", "missing_data")
            and date.weekday() not in self.expected_days
        )

    def is_treatment_start_date(self, date):
        return self.episode_properties.get('treatment_initiation_date') == date.strftime(SERVER_DATE_FORMAT)


class Week(object):
    def __init__(self, days):
        assert len(days) == 7
        weekdays = [6, 0, 1, 2, 3, 4, 5]  # Sunday, Monday, ...
        for i, day in enumerate(days):
            if day:
                assert day.date.weekday() == weekdays[i]
        self.days = days


class Day(object):

    def __init__(self, date, adherence_image_key, show_unexpected_image, show_conflicting_data,
                 show_treatment_start_date, force_month_label=False):
        self.date = date
        self.month_string = self.date.strftime("%b") if self.date.day == 1 or force_month_label else ""
        self.day_string = self.date.day
        self.adherence_image_key = adherence_image_key
        self.show_unexpected_image = show_unexpected_image
        self.show_conflicting_data = show_conflicting_data
        self.show_treatment_start_date = show_treatment_start_date
