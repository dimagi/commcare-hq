from collections import defaultdict, namedtuple
import datetime
from urllib import urlencode
import math
import operator
from pygooglechart import ScatterChart
import pytz

from corehq import toggles
from corehq.apps.es import filters
from corehq.apps.es import cases as case_es
from corehq.apps.es.aggregations import (
    TermsAggregation,
    FilterAggregation,
    MissingAggregation,
)
from corehq.apps.reports import util
from corehq.apps.reports.analytics.esaccessors import (
    get_last_submission_time_for_users,
    get_submission_counts_by_user,
    get_completed_counts_by_user,
    get_submission_counts_by_date,
    get_completed_counts_by_date,
    get_case_counts_closed_by_user,
    get_case_counts_opened_by_user,
    get_active_case_counts_by_owner,
    get_total_case_counts_by_owner,
    get_forms,
    get_form_duration_stats_by_user,
    get_form_duration_stats_for_users)
from corehq.apps.reports.exceptions import TooMuchDataError
from corehq.apps.reports.filters.users import ExpandedMobileWorkerFilter as EMWF
from corehq.apps.reports.standard import ProjectReportParametersMixin, \
    DatespanMixin, ProjectReport
from corehq.apps.reports.filters.forms import CompletionOrSubmissionTimeFilter, FormsByApplicationFilter
from corehq.apps.reports.filters.select import CaseTypeFilter
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType, DataTablesColumnGroup
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.models import HQUserType
from corehq.apps.reports.util import friendly_timedelta, format_datatables_data
from corehq.apps.reports.analytics.esaccessors import get_form_counts_by_user_xmlns
from corehq.apps.users.models import CommCareUser
from corehq.const import SERVER_DATETIME_FORMAT
from corehq.util import flatten_list
from corehq.util.timezones.conversions import ServerTime, PhoneTime
from corehq.util.view_utils import absolute_reverse
from dimagi.utils.couch.safe_index import safe_index
from dimagi.utils.dates import DateSpan, today_or_tomorrow
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import json_format_date, string_to_utc_datetime
from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop


TOO_MUCH_DATA = ugettext_noop(
    'The filters you selected include too much data. Please change your filters and try again'
)

WorkerActivityReportData = namedtuple('WorkerActivityReportData', [
    'avg_submissions_by_user',
    'submissions_by_user',
    'active_cases_by_owner',
    'total_cases_by_owner',
    'cases_closed_by_user',
    'cases_opened_by_user',
])


class WorkerMonitoringReportTableBase(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    exportable = True

    def get_user_link(self, user):
        user_link = self.get_raw_user_link(user)
        return self.table_cell(user.raw_username, user_link)

    def get_raw_user_link(self, user):
        raise NotImplementedError


class WorkerMonitoringCaseReportTableBase(WorkerMonitoringReportTableBase):
    exportable = True

    def get_raw_user_link(self, user):
        user_link_template = '<a href="%(link)s?%(params)s">%(username)s</a>'
        user_link = user_link_template % {
            'link': self.raw_user_link_url,
            'params': urlencode(EMWF.for_user(user.user_id)),
            'username': user.username_in_report,
        }
        return user_link

    @property
    def raw_user_link_url(self):
        from corehq.apps.reports.standard.cases.basic import CaseListReport
        return CaseListReport.get_url(domain=self.domain)


class WorkerMonitoringFormReportTableBase(WorkerMonitoringReportTableBase):

    def get_raw_user_link(self, user):
        params = {
            "form_unknown": self.request.GET.get("form_unknown", ''),
            "form_unknown_xmlns": self.request.GET.get("form_unknown_xmlns", ''),
            "form_status": self.request.GET.get("form_status", ''),
            "form_app_id": self.request.GET.get("form_app_id", ''),
            "form_module": self.request.GET.get("form_module", ''),
            "form_xmlns": self.request.GET.get("form_xmlns", ''),
            "startdate": self.request.GET.get("startdate", ''),
            "enddate": self.request.GET.get("enddate", '')
        }

        params.update(EMWF.for_user(user.user_id))

        from corehq.apps.reports.standard.inspect import SubmitHistory

        user_link_template = '<a href="%(link)s">%(username)s</a>'
        base_link = SubmitHistory.get_url(domain=self.domain)
        link = "{baselink}?{params}".format(baselink=base_link, params=urlencode(params))
        return user_link_template % {
            'link': link,
            'username': user.username_in_report,
        }


class MultiFormDrilldownMixin(object):
    """
        This is a useful mixin when you use FormsByApplicationFilter.
    """

    @property
    @memoized
    def all_relevant_forms(self):
        return FormsByApplicationFilter.get_value(self.request, self.domain)


class CompletionOrSubmissionTimeMixin(object):
    """
        Use this when you use CompletionOrSubmissionTimeFilter.
    """
    @property
    def by_submission_time(self):
        value = CompletionOrSubmissionTimeFilter.get_value(self.request, self.domain)
        return value == 'submission'


class CaseActivityReport(WorkerMonitoringCaseReportTableBase):
    """See column headers for details"""
    name = ugettext_noop('Case Activity')
    slug = 'case_activity'
    fields = ['corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
              'corehq.apps.reports.filters.select.CaseTypeFilter']
    all_users = None
    display_data = ['percent']
    emailable = True
    description = ugettext_noop("Followup rates on active cases.")
    is_cacheable = True
    ajax_pagination = True
    exportable_all = True

    @property
    def shared_pagination_GET_params(self):
        params = [
            dict(
                name=EMWF.slug,
                value=EMWF.get_value(self.request, self.domain)),
            dict(
                name=CaseTypeFilter.slug,
                value=CaseTypeFilter.get_value(self.request, self.domain)),
            dict(
                name='milestone',
                value=self.request.GET.get('milestone')
            ),
            dict(
                name='landmark',
                value=self.request.GET.get('landmark')
            )
        ]
        return params

    @property
    def landmark_columns(self):
        return [
            (_("# Updated or Closed"),
             _("The number of cases that have been created, updated, or closed "
               "between {} days ago and today.")),
            (_("# Active"),
             _("The number of open cases created or updated in the last {} days.")),
            (_("# Closed"),
             _("The number of cases that have been closed between {} days ago and "
               "today.")),
            (_("Proportion"),
             _("The percentage of all recently active cases that were created, "
               "updated or closed in the last {} days.")),
            # "recently active" means "touched in the last 120 days"
        ]

    @property
    def totals_columns(self):
        return [
            (_("# Active Cases"),
             _("Number of open cases modified in the last {} days")),
            (_("# Inactive Cases"),
             _("Number of cases that are open but haven't been touched in the "
               "last {} days")),
        ]

    @property
    def special_notice(self):
        if self.domain_object.case_sharing_included():
            return _("This report currently does not support case sharing. "
                     "There might be inconsistencies in case totals if the "
                     "user is part of a case sharing group.")

    _default_landmarks = [30, 60, 90]

    @property
    @memoized
    def landmarks(self):
        landmarks_param = self.request_params.get('landmarks')
        landmarks_param = landmarks_param if isinstance(landmarks_param, list) else []
        landmarks_param = [param for param in landmarks_param if isinstance(param, int)]
        landmarks = landmarks_param if landmarks_param else self._default_landmarks
        return [('landmark_' + str(idx), datetime.timedelta(days=l)) for idx, l in enumerate(landmarks)]

    _default_milestone = 120

    @property
    @memoized
    def milestone(self):
        milestone_param = self.request_params.get('milestone')
        milestone_param = milestone_param if isinstance(milestone_param, int) else None
        milestone = milestone_param if milestone_param else self._default_milestone
        return datetime.timedelta(days=milestone)

    @property
    @memoized
    def utc_now(self):
        # Fun story:
        # this function was wrong since 2012. Through a convoluted series
        # of refactors where no one was really thinking hard about this
        # it at some point morphed into translating by self.timezone
        # in the opposite direction.
        # Additionally, when I (Danny) re-wrote this report in 2012
        # I had no conception that the dates were suffering from this
        # timezone stripping problem, and so I hadn't factored that in.
        # As a result, this was two timezones off from correct
        # and no one noticed all these years...
        return datetime.datetime.utcnow()

    @property
    def total_records(self):
        return len(self.user_ids)

    @property
    def headers(self):

        def make_column(title, help_text, num_days):
            return DataTablesColumn(title, sort_type=DTSortType.NUMERIC,
                                    help_text=help_text.format(num_days),
                                    sortable=False if title == "Proportion" else True)


        columns = [DataTablesColumn(_("Users"))]

        for __, landmark in self.landmarks:
            columns.append(DataTablesColumnGroup(
                _("Cases in Last {} Days").format(landmark.days) if landmark else _("Ever"),
                *[make_column(title, help_text, landmark.days)
                  for title, help_text in self.landmark_columns]
            ))

        for title, help_text in self.totals_columns:
            columns.append(make_column(title, help_text, self.milestone.days))

        return DataTablesHeader(*columns)

    @property
    @memoized
    def all_users(self):
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
        users_data = EMWF.pull_users_and_groups(
            self.domain,
            mobile_user_and_group_slugs,
        )
        return users_data.combined_users

    @property
    @memoized
    def users_by_id(self):
        return {user.user_id: user for user in self.all_users}

    @property
    @memoized
    def user_ids(self):
        return self.users_by_id.keys()

    @property
    @memoized
    def paginated_users(self):
        if self.sort_column is None:
            return sorted(
                self.all_users, key=lambda u: u.raw_username, reverse=self.pagination.desc
            )[self.pagination.start:self.pagination.start + self.pagination.count]
        return self.all_users

    @property
    @memoized
    def paginated_users_by_id(self):
        return [(user.user_id, user) for user in self.paginated_users]

    @property
    @memoized
    def paginated_user_ids(self):
        return [user.user_id for user in self.paginated_users]

    @property
    def sort_column(self):
        column_num = self.request_params.get('iSortCol_0', 0)
        num_columns = self.request_params.get('iColumns', 15)
        if column_num == 0:
            return None  # user
        elif column_num == (num_columns - 2):
            return "active_total"
        elif column_num == (num_columns - 1):
            return "inactive_total"
        else:
            landmark = column_num // 4
            sub_col = column_num % 4
            if sub_col == 1:
                column = ""  # this will sort by doc_count
            elif sub_col == 2:
                column = "active"
            elif sub_col == 3:
                column = "closed"
            else:
                return None  # Can't actually select this in the UI

        if column:
            return "landmark_%d>%s" % (landmark, column)
        else:
            return "landmark_%d" % (landmark,)

    @property
    def should_sort_by_username(self):
        return self.request_params.get('iSortCol_0', 0) == 0

    def _format_row(self, row):
        cells = [row.header()]
        total_touched = row.total_touched_count()

        for landmark_key, landmark in self.landmarks:
            modified = row.modified_count(landmark_key)
            active = row.active_count(landmark_key)
            closed = row.closed_count(landmark_key)

            try:
                p_val = float(modified) * 100. / float(total_touched)
                proportion = '%.f%%' % p_val
            except ZeroDivisionError:
                p_val = None
                proportion = '--'

            cells.append(modified)
            cells.append(active)
            cells.append(closed)
            cells.append(proportion)

        cells.append(row.total_active_count())
        cells.append(row.total_inactive_count())
        return cells

    @property
    def rows(self):
        es_results = self.es_queryset(
            user_ids=self.paginated_user_ids,
            size=self.pagination.start + self.pagination.count
        )
        buckets = es_results.aggregations.users.buckets_list
        if self.missing_users:
            buckets.append(es_results.aggregations.missing_users.bucket)
        rows = []
        for bucket in buckets:
            user = self.users_by_id[bucket.key]
            rows.append(self.Row(self, user, bucket))

        rows.extend(self._unmatched_buckets(buckets, self.paginated_user_ids))

        if self.should_sort_by_username:
            # ES handles sorting for all other columns
            rows.sort(key=lambda row: row.user.raw_username)

        self.total_row = self._total_row
        if len(rows) <= self.pagination.count:
            return map(self._format_row, rows)
        else:
            start = self.pagination.start
            end = start + self.pagination.count
            paginated_rows = rows[start:end]
            return map(self._format_row, paginated_rows)

    @property
    def get_all_rows(self):
        es_results = self.es_queryset(user_ids=self.user_ids)
        buckets = es_results.aggregations.users.buckets_list
        if self.missing_users:
            buckets.append(es_results.aggregations.missing_users.bucket)
        rows = []
        for bucket in buckets:
            user = self.users_by_id[bucket.key]
            rows.append(self.Row(self, user, bucket))

        rows.extend(self._unmatched_buckets(buckets, self.user_ids))

        self.total_row = self._total_row
        return map(self._format_row, rows)

    def _unmatched_buckets(self, buckets, user_ids):
        # ES doesn't return buckets that don't have any docs matching docs
        # we expect a bucket for each relevant user id so add empty buckets
        returned_user_ids = {b.key for b in buckets}
        not_returned_user_ids = set(user_ids) - returned_user_ids
        extra_rows = []
        for user_id in not_returned_user_ids:
            extra_rows.append(self.Row(self, self.users_by_id[user_id], {}))
        extra_rows.sort(key=lambda row: row.user.raw_username)
        return extra_rows

    @property
    def _touched_total_aggregation(self):
        return case_es.touched_total_aggregation(gte=self.milestone_start, lt=self.end_date)

    @property
    def _active_total_aggregation(self):
        return case_es.open_case_aggregation(name='active_total', gte=self.milestone_start, lt=self.end_date)

    @property
    def _inactive_total_aggregation(self):
        return case_es.open_case_aggregation(name='inactive_total', lt=self.milestone_start)

    @property
    def _total_row(self):
        query = (
            case_es.CaseES()
            .domain(self.domain)
            .user_ids_handle_unknown(self.user_ids)
            .size(0)
        )
        if self.case_type:
            query = query.filter(case_es.case_type(self.case_type))
        else:
            query = query.filter(filters.NOT(case_es.case_type('commcare-user')))

        query = (
            query
            .aggregation(self._touched_total_aggregation)
            .aggregation(self._active_total_aggregation)
            .aggregation(self._inactive_total_aggregation)
        )

        query = self.add_landmark_aggregations(query, self.end_date)

        return self._format_row(self.TotalRow(query.run(), _("All Users")))

    @property
    @memoized
    def missing_users(self):
        return None in self.user_ids

    @property
    def end_date(self):
        return ServerTime(self.utc_now).phone_time(self.timezone).done()

    @property
    def milestone_start(self):
        return ServerTime(self.utc_now - self.milestone).phone_time(self.timezone).done()

    def es_queryset(self, user_ids, size=None):
        top_level_aggregation = (
            TermsAggregation('users', 'user_id')
            .aggregation(self._touched_total_aggregation)
            .aggregation(self._active_total_aggregation)
            .aggregation(self._inactive_total_aggregation)
        )

        top_level_aggregation = self.add_landmark_aggregations(top_level_aggregation, self.end_date)

        if size:
            top_level_aggregation = top_level_aggregation.size(size)

        if self.sort_column:
            order = "desc" if self.pagination.desc else "asc"
            top_level_aggregation = top_level_aggregation.order(self.sort_column, order)
            top_level_aggregation = top_level_aggregation.order("_term", order, reset=False)

        query = (
            case_es.CaseES()
            .domain(self.domain)
            .user_ids_handle_unknown(user_ids)
            .size(0)
        )
        if self.case_type:
            query = query.case_type(self.case_type)
        else:
            query = query.filter(filters.NOT(case_es.case_type('commcare-user')))

        query = query.aggregation(top_level_aggregation)

        if self.missing_users:
            missing_aggregation = (
                MissingAggregation('missing_users', 'user_id')
                .aggregation(self._touched_total_aggregation)
                .aggregation(self._active_total_aggregation)
                .aggregation(self._inactive_total_aggregation)
            )
            missing_aggregation = self.add_landmark_aggregations(missing_aggregation, self.end_date)
            query = query.aggregation(missing_aggregation)

        return query.run()

    def add_landmark_aggregations(self, aggregation, end_date):
        for key, landmark in self.landmarks:
            aggregation = aggregation.aggregation(self.landmark_aggregation(key, landmark, end_date))
        return aggregation

    def landmark_aggregation(self, key, landmark, end_date):
        start_date = ServerTime(self.utc_now - landmark).phone_time(self.timezone).done()
        return (
            FilterAggregation(key,
                filters.AND(
                    case_es.modified_range(gte=start_date, lt=end_date),
                )
            )
            .aggregation(FilterAggregation('active', case_es.is_closed(False)))
            .aggregation(FilterAggregation('closed', case_es.is_closed()))
        )

    class Row(object):

        def __init__(self, report, user, bucket):
            self.report = report
            self.user = user
            self.bucket = bucket

        def active_count(self, landmark_key):
            if not self.bucket:
                return 0
            else:
                landmark = self.bucket.result.get(landmark_key, None)
                if landmark:
                    return landmark['active']['doc_count']
                return 0

        def modified_count(self, landmark_key):
            if not self.bucket:
                return 0
            else:
                landmark = self.bucket.result.get(landmark_key, None)
                if landmark:
                    return landmark['doc_count']
                return 0

        def closed_count(self, landmark_key):
            if not self.bucket:
                return 0
            else:
                landmark = self.bucket.result.get(landmark_key, None)
                if landmark:
                    return landmark['closed']['doc_count']
                return 0

        def total_touched_count(self):
            if not self.bucket:
                return 0
            else:
                landmark = self.bucket.result.get('touched_total', None)
                if landmark:
                    return landmark['doc_count']
                return 0

        def total_inactive_count(self):
            if not self.bucket:
                return 0
            else:
                landmark = self.bucket.result.get('inactive_total', None)
                if landmark:
                    return landmark['doc_count']
                return 0

        def total_active_count(self):
            if not self.bucket:
                return 0
            else:
                landmark = self.bucket.result.get('active_total', None)
                if landmark:
                    return landmark['doc_count']
                return 0

        def header(self):
            return self.report.get_user_link(self.user)['html']

    class TotalRow(object):

        def __init__(self, es_results, header):
            self._header = header
            self.total_touched_bucket = es_results.aggregations.touched_total
            self.total_active_bucket = es_results.aggregations.active_total
            self.total_inactive_bucket = es_results.aggregations.inactive_total
            self.aggregations = es_results.aggregations

        def total_touched_count(self):
            return self.total_touched_bucket.doc_count

        def total_inactive_count(self):
            return self.total_inactive_bucket.doc_count

        def total_active_count(self):
            return self.total_active_bucket.doc_count

        def active_count(self, landmark_key):
            return getattr(self.aggregations, landmark_key).result['active']['doc_count']

        def modified_count(self, landmark_key):
            return getattr(self.aggregations, landmark_key).doc_count

        def closed_count(self, landmark_key):
            return getattr(self.aggregations, landmark_key).result['closed']['doc_count']

        def header(self):
            return self._header


class SubmissionsByFormReport(WorkerMonitoringFormReportTableBase,
                              MultiFormDrilldownMixin, DatespanMixin,
                              CompletionOrSubmissionTimeMixin):
    name = ugettext_noop("Submissions By Form")
    slug = "submissions_by_form"
    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter'
    ]
    fix_left_col = True
    emailable = True
    is_cacheable = True
    description = ugettext_noop("Number of submissions by form.")

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        if project and project.commtrack_enabled:
            return False
        else:
            return True

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn(_("User"), span=3))
        if not self.all_relevant_forms:
            headers.add_column(
                DataTablesColumn(
                    _("No submissions were found for selected forms "
                      "within this date range."),
                    sortable=False
                )
            )
        else:
            for _form, info in self.all_relevant_forms.items():
                help_text = None
                if info['is_fuzzy']:
                    help_text = _("This column shows Fuzzy Submissions.")
                headers.add_column(
                    DataTablesColumn(
                        info['name'],
                        sort_type=DTSortType.NUMERIC,
                        help_text=help_text,
                    )
                )
            headers.add_column(
                DataTablesColumn(_("All Forms"), sort_type=DTSortType.NUMERIC)
            )
        return headers

    @property
    @memoized
    def selected_users(self):
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
        users_data = EMWF.pull_users_and_groups(
            self.domain,
            mobile_user_and_group_slugs,
        )
        return users_data.combined_users

    @property
    def rows(self):
        rows = []
        totals = [0] * (len(self.all_relevant_forms) + 1)
        for user in self.selected_users:
            row = []
            if self.all_relevant_forms:
                for form in self.all_relevant_forms.values():
                    row.append(self._form_counts[
                        (user.user_id, form['app_id'], form['xmlns'].lower())
                    ])
                row_sum = sum(row)
                row = (
                    [self.get_user_link(user)] +
                    [self.table_cell(row_data, zerostyle=True) for row_data in row] +
                    [self.table_cell(row_sum, "<strong>%s</strong>" % row_sum)]
                )
                totals = [totals[i] + col.get('sort_key')
                          for i, col in enumerate(row[1:])]
                rows.append(row)
            else:
                rows.append([self.get_user_link(user), '--'])
        if self.all_relevant_forms:
            self.total_row = [_("All Users")] + totals
        return rows

    @property
    @memoized
    def _form_counts(self):
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
        if EMWF.show_all_mobile_workers(mobile_user_and_group_slugs):
            user_ids = []
        else:
            # Don't query ALL mobile workers
            user_ids = [u.user_id for u in self.selected_users]
        return get_form_counts_by_user_xmlns(
            domain=self.domain,
            startdate=self.datespan.startdate_utc.replace(tzinfo=pytz.UTC),
            enddate=self.datespan.enddate_utc.replace(tzinfo=pytz.UTC),
            user_ids=user_ids,
            xmlnss=[f['xmlns'] for f in self.all_relevant_forms.values()],
            by_submission_time=self.by_submission_time,
        )


class DailyFormStatsReport(WorkerMonitoringCaseReportTableBase, CompletionOrSubmissionTimeMixin, DatespanMixin):
    slug = "daily_form_stats"
    name = ugettext_noop("Daily Form Activity")
    bad_request_error_text = ugettext_noop("Your search query was invalid. If you're using a large date range, try using a smaller one.")

    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter',
    ]

    description = ugettext_noop("Number of submissions per day.")

    fix_left_col = False
    emailable = True
    is_cacheable = False
    ajax_pagination = True
    exportable_all = True
    datespan_max_days = 90

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        if project and project.commtrack_enabled:
            return False
        else:
            return True

    @property
    @memoized
    def dates(self):
        date_list = [self.datespan.startdate]
        while date_list[-1] < self.datespan.enddate:
            date_list.append(date_list[-1] + datetime.timedelta(days=1))
        return date_list

    @property
    def headers(self):
        if self.datespan.is_valid():
            headers = DataTablesHeader(DataTablesColumn(_("Username"), span=3))
            for d in self.dates:
                headers.add_column(DataTablesColumn(json_format_date(d), sort_type=DTSortType.NUMERIC))
            headers.add_column(DataTablesColumn(_("Total"), sort_type=DTSortType.NUMERIC))
            return headers
        else:
            return DataTablesHeader(DataTablesColumn(_("Error")))

    @property
    def date_field(self):
        return 'received_on' if self.by_submission_time else 'time_end'

    @property
    def startdate(self):
        return self.datespan.startdate_utc if self.by_submission_time else self.datespan.startdate

    @property
    def enddate(self):
        return self.datespan.enddate_utc if self.by_submission_time else self.datespan.enddate_adjusted

    @property
    def is_submission_time(self):
        return self.date_field == 'received_on'

    def date_filter(self, start, end):
        return {'%s__range' % self.date_field: (start, end)}

    @property
    def shared_pagination_GET_params(self):
        params = [
            dict(
                name=EMWF.slug,
                value=EMWF.get_value(self.request, self.domain)),
            dict(
                name=CompletionOrSubmissionTimeFilter.slug,
                value=CompletionOrSubmissionTimeFilter.get_value(self.request, self.domain)),
            dict(name='startdate', value=self.datespan.startdate_display),
            dict(name='enddate', value=self.datespan.enddate_display),
        ]
        return params

    @property
    def total_records(self):
        return len(self.all_users)

    @property
    @memoized
    def all_users(self):
        user_query = EMWF.user_es_query(self.domain, self.request.GET.getlist(EMWF.slug))
        return util.get_simplified_users(user_query)

    def paginate_list(self, data_list):
        if self.pagination:
            start = self.pagination.start
            end = start + self.pagination.count
            return data_list[start:end]
        else:
            return data_list

    def users_by_username(self, order):
        users = self.all_users
        if order == "desc":
            users.reverse()
        return self.paginate_list(users)

    def users_by_range(self, datespan, order):
        if self.is_submission_time:
            get_counts_by_user = get_submission_counts_by_user
        else:
            get_counts_by_user = get_completed_counts_by_user

        results = get_counts_by_user(
            self.domain,
            datespan,
        )

        return self.users_sorted_by_count(results, order)

    def users_sorted_by_count(self, count_dict, order):
        # Split all_users into those in count_dict and those not.
        # Sort the former by count and return
        users_with_forms = []
        users_without_forms = []
        for user in self.all_users:
            u_id = user['user_id']
            if u_id in count_dict:
                users_with_forms.append((count_dict[u_id], user))
            else:
                users_without_forms.append(user)
        if order == "asc":
            users_with_forms.sort()
            sorted_users = users_without_forms
            sorted_users += map(lambda u: u[1], users_with_forms)
        else:
            users_with_forms.sort(reverse=True)
            sorted_users = map(lambda u: u[1], users_with_forms)
            sorted_users += users_without_forms

        return self.paginate_list(sorted_users)

    @property
    def column_count(self):
        return len(self.dates) + 2

    @property
    def rows(self):
        if not self.datespan.is_valid():
            return [[self.datespan.get_validation_reason()]]

        self.sort_col = self.request_params.get('iSortCol_0', 0)
        totals_col = self.column_count - 1
        order = self.request_params.get('sSortDir_0')

        if self.sort_col == totals_col:
            users = self.users_by_range(self.datespan, order)
        elif 0 < self.sort_col < totals_col:
            start = self.dates[self.sort_col - 1]
            end = start + datetime.timedelta(days=1)
            users = self.users_by_range(DateSpan(start, end), order)
        else:
            users = self.users_by_username(order)

        rows = [self.get_row(user) for user in users]
        self.total_row = self.get_row()
        return rows

    @property
    def get_all_rows(self):
        rows = [self.get_row(user) for user in self.all_users]
        self.total_row = self.get_row()
        return rows

    def get_row(self, user=None):
        """
        Assemble a row for a given user.
        If no user is passed, assemble a totals row.
        """
        user_ids = map(lambda user: user.user_id, [user] if user else self.all_users)

        if self.is_submission_time:
            get_counts_by_date = get_submission_counts_by_date
        else:
            get_counts_by_date = get_completed_counts_by_date

        results = get_counts_by_date(
            self.domain,
            user_ids,
            self.datespan,
            self.timezone,
        )

        date_cols = [
            results.get(json_format_date(date), 0)
            for date in self.dates
        ]
        styled_date_cols = ['<span class="muted">0</span>' if c == 0 else c for c in date_cols]
        first_col = self.get_raw_user_link(user) if user else _("Total")
        return [first_col] + styled_date_cols + [sum(date_cols)]

    @property
    def raw_user_link_url(self):
        from corehq.apps.reports.standard.inspect import SubmitHistory
        return SubmitHistory.get_url(domain=self.domain)

    @property
    def template_context(self):
        context = super(DailyFormStatsReport, self).template_context
        context.update({
            'hide_lastyear': True,
        })
        return context


class FormCompletionTimeReport(WorkerMonitoringFormReportTableBase, DatespanMixin,
                               CompletionOrSubmissionTimeMixin):
    name = ugettext_noop("Form Completion Time")
    slug = "completion_times"
    fields = ['corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
              'corehq.apps.reports.filters.forms.SingleFormByApplicationFilter',
              'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    description = ugettext_noop("Statistics on time spent on a particular form.")
    is_cacheable = True

    @property
    @memoized
    def selected_form_data(self):
        forms = FormsByApplicationFilter.get_value(self.request, self.domain).values()
        if len(forms) == 1 and forms[0]['xmlns']:
            return forms[0]
        non_fuzzy_forms = [form for form in forms if not form['is_fuzzy']]
        if len(non_fuzzy_forms) == 1:
            return non_fuzzy_forms[0]

    @property
    def headers(self):
        if not self.selected_form_data:
            return DataTablesHeader(DataTablesColumn(_("No Form Selected"), sortable=False))
        return DataTablesHeader(DataTablesColumn(_("User")),
            DataTablesColumn(_("Average"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Std. Dev."), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Shortest"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("Longest"), sort_type=DTSortType.NUMERIC),
            DataTablesColumn(_("No. of Forms"), sort_type=DTSortType.NUMERIC))

    @property
    def rows(self):
        rows = []
        if not self.selected_form_data:
            rows.append([_("You must select a specific form to view data.")])
            return rows

        def to_duration(val_in_s):
            assert val_in_s is not None
            return datetime.timedelta(milliseconds=val_in_s)

        def to_minutes(val_in_s):
            if val_in_s is None:
                return "--"
            return friendly_timedelta(to_duration(val_in_s))

        def to_minutes_raw(val_in_s):
            """
            return a timestamp like 66:12:24 (the first number is hours
            """
            if val_in_s is None:
                return '--'
            td = to_duration(val_in_s)
            hours, remainder = divmod(td.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return '{h}:{m}:{s}'.format(
                h=(td.days * 24) + hours,
                m=minutes,
                s=seconds,
            )

        def _fmt_ts(timestamp):
            return format_datatables_data(to_minutes(timestamp), timestamp, to_minutes_raw(timestamp))

        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
        users_data = EMWF.pull_users_and_groups(
            self.domain,
            mobile_user_and_group_slugs,
        )
        user_ids = [user.user_id for user in users_data.combined_users]
        app_id = self.selected_form_data['app_id']
        xmlns = self.selected_form_data['xmlns']

        data_map = get_form_duration_stats_by_user(
            self.domain,
            app_id,
            xmlns,
            user_ids,
            self.datespan.startdate_utc,
            self.datespan.enddate_utc,
            by_submission_time=self.by_submission_time,
        )

        for user in users_data.combined_users:
            stats = data_map.get(user.user_id, {})
            rows.append([
                self.get_user_link(user),
                _fmt_ts(stats.get('avg')),
                _fmt_ts(stats.get('std_deviation')),
                _fmt_ts(stats.get('min')),
                _fmt_ts(stats.get('max')),
                stats.get('count', 0),
            ])

        total_data = get_form_duration_stats_for_users(
            self.domain,
            app_id,
            xmlns,
            user_ids,
            self.datespan.startdate_utc,
            self.datespan.enddate_utc,
            by_submission_time=self.by_submission_time,
        )
        self.total_row = ["All Users",
                          _fmt_ts(total_data.get('avg')),
                          _fmt_ts(total_data.get('std_deviation')),
                          _fmt_ts(total_data.get('min')),
                          _fmt_ts(total_data.get('max')),
                          total_data.get('count', 0)]
        return rows


class FormCompletionVsSubmissionTrendsReport(WorkerMonitoringFormReportTableBase,
                                             MultiFormDrilldownMixin, DatespanMixin):
    name = ugettext_noop("Form Completion vs. Submission Trends")
    slug = "completion_vs_submission"
    is_cacheable = True

    description = ugettext_noop("Time lag between when forms were completed and when forms were successfully "
                                "sent to CommCare HQ.")

    fields = ['corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
              'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
              'corehq.apps.reports.filters.dates.DatespanFilter']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn(_("User")),
            DataTablesColumn(_("Completion Time"), sort_type=DTSortType.DATE),
            DataTablesColumn(_("Submission Time"), sort_type=DTSortType.DATE),
            DataTablesColumn(_("Form Name")),
            DataTablesColumn(_("View"), sortable=False),
            DataTablesColumn(_("Difference"), sort_type=DTSortType.NUMERIC)
        )

    @property
    def rows(self):
        try:
            return self._get_rows()
        except TooMuchDataError as e:
            return [['<span class="label label-danger">{}</span>'.format(e)] + ['--'] * 5]

    def _get_rows(self):
        rows = []
        total = 0
        total_seconds = 0
        if self.all_relevant_forms:
            mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
            users_data = EMWF.pull_users_and_groups(
                self.domain,
                mobile_user_and_group_slugs,
            )

            user_map = {user.user_id: user
                        for user in users_data.combined_users if user.user_id}
            user_ids = [user.user_id for user in users_data.combined_users if user.user_id]

            xmlnss = []
            app_ids = []
            form_map = {}

            for form in self.all_relevant_forms.values():
                xmlnss.append(form['xmlns'])
                if form['app_id']:
                    app_ids.append(form['app_id'])
                form_map[form['xmlns']] = form['name']

            paged_result = get_forms(
                self.domain,
                self.datespan.startdate_utc.date(),
                self.datespan.enddate_utc.date(),
                user_ids=user_ids,
                app_ids=app_ids,
                xmlnss=xmlnss,
            )
            for row in paged_result.hits:
                completion_time = (PhoneTime(
                    string_to_utc_datetime(row['form']['meta']['timeEnd']),
                    self.timezone,
                ).server_time().done())
                submission_time = string_to_utc_datetime(row['received_on'])
                td = submission_time - completion_time
                td_total = (td.seconds + td.days * 24 * 3600)
                rows.append([
                    self.get_user_link(user_map.get(row['form']['meta']['userID'])),
                    self._format_date(completion_time),
                    self._format_date(submission_time),
                    form_map[row['xmlns']],
                    self._view_form_link(row['_id']),
                    self.table_cell(td_total, self._format_td_status(td))
                ])

                if td_total >= 0:
                    total_seconds += td_total
                    total += 1
        else:
            rows.append(['No Submissions Available for this Date Range'] + ['--']*5)

        self.total_row = [_("Average"), "-", "-", "-", "-", self._format_td_status(int(total_seconds/total), False) if total > 0 else "--"]
        return rows

    def _format_date(self, date):
        """
        date is a datetime
        """

        return self.table_cell(
            ServerTime(date).user_time(self.timezone).ui_string(fmt=SERVER_DATETIME_FORMAT),
            ServerTime(date).user_time(self.timezone).ui_string(),
        )

    def _format_td_status(self, td, use_label=True):
        status = list()
        template = '<span class="label %(klass)s">%(status)s</span>'
        klass = "label-default"
        if isinstance(td, int):
            td = datetime.timedelta(seconds=td)
        if isinstance(td, datetime.timedelta):
            hours = td.seconds//3600
            minutes = (td.seconds//60)%60
            vals = [td.days, hours, minutes, (td.seconds - hours*3600 - minutes*60)]
            names = [_("day"), _("hour"), _("minute"), _("second")]
            status = ["%s %s%s" % (val, names[i], "s" if val != 1 else "") for (i, val) in enumerate(vals) if val > 0]

            if td.days > 1:
                klass = "label-danger"
            elif td.days == 1:
                klass = "label-warning"
            elif hours > 5:
                klass = "label-primary"
            if not status:
                status.append("same")
            elif td.days < 0:
                if abs(td).seconds > 15*60:
                    status = [_("submitted before completed [strange]")]
                    klass = "label-info"
                else:
                    status = [_("same")]

        if use_label:
            return template % dict(status=", ".join(status), klass=klass)
        else:
            return ", ".join(status)

    def _view_form_link(self, instance_id):
        return '<a class="btn btn-default" href="%s">View Form</a>' % absolute_reverse(
            'render_form_data', args=[self.domain, instance_id])


class WorkerMonitoringChartBase(ProjectReport, ProjectReportParametersMixin):
    flush_layout = True
    report_template_path = "reports/async/basic.html"


class WorkerActivityTimes(WorkerMonitoringChartBase,
    MultiFormDrilldownMixin, CompletionOrSubmissionTimeMixin, DatespanMixin):
    name = ugettext_noop("Worker Activity Times")
    slug = "worker_activity_times"
    is_cacheable = True

    description = ugettext_noop("Graphical representation of when forms are "
                                "completed or submitted.")

    fields = [
        'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
        'corehq.apps.reports.filters.forms.FormsByApplicationFilter',
        'corehq.apps.reports.filters.forms.CompletionOrSubmissionTimeFilter',
        'corehq.apps.reports.filters.dates.DatespanFilter']

    report_partial_path = "reports/partials/punchcard.html"

    @property
    @memoized
    def activity_times(self):
        all_times = []
        mobile_user_and_group_slugs = self.request.GET.getlist(EMWF.slug)
        users_data = EMWF.pull_users_and_groups(
            self.domain,
            mobile_user_and_group_slugs,
        )
        user_ids = map(lambda user: user.user_id, users_data.combined_users)
        xmlnss = map(lambda form: form['xmlns'], self.all_relevant_forms.values())
        app_ids = map(lambda form: form['app_id'], self.all_relevant_forms.values())

        paged_result = get_forms(
            self.domain,
            self.datespan.startdate_utc,
            self.datespan.enddate_utc,
            user_ids=user_ids,
            app_ids=app_ids,
            xmlnss=xmlnss,
            by_submission_time=self.by_submission_time,
        )
        if paged_result.total > 5000:
            raise TooMuchDataError()

        all_times = []

        for form in paged_result.hits:
            if self.by_submission_time:
                all_times.append(
                    ServerTime(string_to_utc_datetime(form['received_on'])).user_time(self.timezone).done()
                )
            else:
                all_times.append(
                    PhoneTime(
                        string_to_utc_datetime(safe_index(form, ['form', 'meta', 'timeEnd'])),
                        self.timezone,
                    )
                    .user_time(self.timezone)
                    .done()
                )

        aggregated_times = defaultdict(int)
        for t in all_times:
            aggregated_times[(t.weekday(), t.hour)] += 1
        return aggregated_times

    @property
    def report_context(self):
        error = None
        try:
            activity_times = self.activity_times
            if len(activity_times) == 0:
                error = _("Note: No submissions matched your filters.")
        except TooMuchDataError:
            activity_times = defaultdict(int)
            error = _(TOO_MUCH_DATA)

        return dict(
            chart_url=self.generate_chart(activity_times, timezone=self.timezone),
            error=error,
            timezone=self.timezone,
        )

    @classmethod
    def generate_chart(cls, data, width=950, height=300, timezone="UTC"):
        """
            Gets a github style punchcard chart.
            Hat tip: http://github.com/dustin/bindir/blob/master/gitaggregates.py
        """
        no_data = not data
        chart = ScatterChart(width, height, x_range=(-1, 24), y_range=(-1, 7))

        chart.add_data([(h % 24) for h in range(24 * 8)])

        d=[]
        for i in range(8):
            d.extend([i] * 24)
        chart.add_data(d)

        # mapping between numbers 0..6 and its day of the week label
        day_names = [_("Mon"), _("Tue"), _("Wed"), _("Thu"), _("Fri"), _("Sat"), _("Sun")]
        # the order, bottom-to-top, in which the days should appear
        # i.e. Sun, Sat, Fri, Thu, etc
        days = (6, 5, 4, 3, 2, 1, 0)

        sizes=[]
        for d in days:
            sizes.extend([data[(d, h)] for h in range(24)])
        sizes.extend([0] * 24)
        if no_data:
            # fill in a line out of view so that chart.get_url() doesn't crash
            sizes.extend([1] * 24)
        chart.add_data(sizes)

        chart.set_axis_labels('x', [''] + [(str(h) + ':00') for h in range(24)] + [''])
        chart.set_axis_labels('x', [' ', _('Time ({timezone})').format(timezone=timezone), ' '])
        # our google charts library doesn't support unicode
        # TODO: replace with some in JS (d3?)
        chart.set_axis_labels('y', [''] + [day_names[n].encode('ascii', 'replace') for n in days] + [''])

        chart.add_marker(1, 1.0, 'o', '333333', 25)
        return chart.get_url() + '&chds=-1,24,-1,7,0,20'


class WorkerActivityReport(WorkerMonitoringCaseReportTableBase, DatespanMixin):
    slug = 'worker_activity'
    name = ugettext_noop("Worker Activity")
    description = ugettext_noop("Summary of form and case activity by user or group.")
    section_name = ugettext_noop("Project Reports")
    num_avg_intervals = 3  # how many duration intervals we go back to calculate averages
    is_cacheable = True

    fix_left_col = True
    emailable = True

    NO_FORMS_TEXT = ugettext_noop('None')

    @property
    def fields(self):
        if toggles.EMWF_WORKER_ACTIVITY_REPORT.enabled(self.request.domain):
            return [
                'corehq.apps.reports.filters.users.ExpandedMobileWorkerFilter',
                'corehq.apps.reports.filters.select.MultiCaseTypeFilter',
                'corehq.apps.reports.filters.dates.DatespanFilter',
            ]
        return [
            'corehq.apps.reports.filters.select.MultiGroupFilter',
            'corehq.apps.reports.filters.users.UserOrGroupFilter',
            'corehq.apps.reports.filters.select.MultiCaseTypeFilter',
            'corehq.apps.reports.filters.dates.DatespanFilter',
        ]

    @classmethod
    def display_in_dropdown(cls, domain=None, project=None, user=None):
        return True

    @property
    def case_types(self):
        return filter(None, self.request.GET.getlist('case_type'))

    @property
    def view_by_groups(self):
        if toggles.EMWF_WORKER_ACTIVITY_REPORT.enabled(self.request.domain):
            return False
        return self.request.GET.get('view_by', None) == 'groups'

    @property
    def headers(self):
        CASE_TYPE_MSG = "The case type filter doesn't affect this column."
        by_group = self.view_by_groups
        columns = [DataTablesColumn(_("Group"))] if by_group else [DataTablesColumn(_("User"))]
        columns.append(DataTablesColumnGroup(_("Form Data"),
            DataTablesColumn(_("# Forms Submitted"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of forms submitted in chosen date range. %s" % CASE_TYPE_MSG)),
            DataTablesColumn(_("Avg # Forms Submitted"), sort_type=DTSortType.NUMERIC,
                help_text=_("Average number of forms submitted in the three preceding date ranges of the same length. %s" % CASE_TYPE_MSG)),
            DataTablesColumn(_("Last Form Submission"),
                help_text=_("Date of last form submission in time period.  Total row displays proportion of users submitting forms in date range")) \
            if not by_group else DataTablesColumn(_("# Active Users"), sort_type=DTSortType.NUMERIC,
                help_text=_("Proportion of users in group who submitted forms in date range."))
        ))
        columns.append(DataTablesColumnGroup(_("Case Data"),
            DataTablesColumn(_("# Cases Created"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of cases created in the date range.")),
            DataTablesColumn(_("# Cases Closed"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of cases closed in the date range.")),
            ))
        columns.append(DataTablesColumnGroup(_("Case Activity"),
            DataTablesColumn(_("# Active Cases"), sort_type=DTSortType.NUMERIC,
                help_text=_("Number of cases owned by the user that were opened, modified or closed in date range.  This includes case sharing cases.")),
            DataTablesColumn(_("# Total Cases"), sort_type=DTSortType.NUMERIC,
                help_text=_("Total number of cases owned by the user.  This includes case sharing cases.")),
            DataTablesColumn(_("% Active Cases"), sort_type=DTSortType.NUMERIC,
                help_text=_("Percentage of cases owned by user that were active.  This includes case sharing cases.")),
        ))
        return DataTablesHeader(*columns)

    @property
    def group_ids(self):
        return [group_id for group_id in self.request.GET.getlist('group')
                if group_id and group_id != '_all']

    @property
    @memoized
    def users_by_group(self):
        from corehq.apps.groups.models import Group

        if not self.group_ids or self.request.GET.get('all_groups', 'off') == 'on':
            groups = Group.get_reporting_groups(self.domain)
        else:
            groups = [Group.get(g) for g in self.group_ids]

        user_dict = {}
        for group in groups:
            user_dict["%s|%s" % (group.name, group._id)] = self.get_all_users_by_domain(
                group=group,
                user_filter=tuple(self.default_user_filter),
                simplified=True
            )

        return user_dict

    def get_users_by_mobile_workers(self):
        from corehq.apps.reports.util import _report_user_dict
        user_dict = {}
        for mw in self.mobile_worker_ids:
            user_dict[mw] = _report_user_dict(CommCareUser.get_by_user_id(mw))

        return user_dict

    def get_admins_and_demo_users(self):
        ufilters = [uf for uf in ['1', '2', '3'] if uf in self.request.GET.getlist('ufilter')]
        return self.get_all_users_by_domain(
            group=None,
            user_filter=tuple(HQUserType.use_filter(ufilters)),
            simplified=True
        ) if ufilters else []

    @property
    def users_to_iterate(self):
        if toggles.EMWF_WORKER_ACTIVITY_REPORT.enabled(self.request.domain):
            user_query = EMWF.user_es_query(self.domain, self.request.GET.getlist(EMWF.slug))
            return util.get_simplified_users(user_query)
        elif not self.group_ids:
            ret = [util._report_user_dict(u) for u in list(CommCareUser.by_domain(self.domain))]
            return ret
        else:
            all_users = flatten_list(self.users_by_group.values())
            all_users.extend([user for user in self.get_users_by_mobile_workers().values()])
            all_users.extend([user for user in self.get_admins_and_demo_users()])
            return dict([(user['user_id'], user) for user in all_users]).values()

    @property
    def user_ids(self):
        return [u["user_id"] for u in self.users_to_iterate]

    def es_last_submissions(self):
        """
        Creates a dict of userid => date of last submission
        """
        return get_last_submission_time_for_users(self.domain, self.user_ids, self.datespan)

    @staticmethod
    def _dates_for_linked_reports(datespan, case_list=False):
        start_date = datespan.startdate_param
        end_date = datespan.enddate if not case_list else datespan.enddate + datetime.timedelta(days=1)
        end_date = end_date.strftime(datespan.format)
        return start_date, end_date

    def _submit_history_link(self, owner_id, value):
        """
        returns a cell that is linked to the submit history report
        """
        base_url = absolute_reverse('project_report_dispatcher', args=(self.domain, 'submit_history'))
        if self.view_by_groups:
            params = EMWF.for_reporting_group(owner_id)
        else:
            params = EMWF.for_user(owner_id)

        start_date, end_date = self._dates_for_linked_reports(self.datespan)
        params.update({
            "startdate": start_date,
            "enddate": end_date,
        })

        return util.numcell(
            self._html_anchor_tag(self._make_url(base_url, params), value),
            value,
        )

    @staticmethod
    def _html_anchor_tag(href, value):
        return u'<a href="{}" target="_blank">{}</a>'.format(href, value)

    @staticmethod
    def _make_url(base_url, params):
        return '{base_url}?{params}'.format(
            base_url=base_url,
            params=urlencode(params, True),
        )

    @staticmethod
    def _case_query(case_type):
        if not case_type:
            return ''
        return ' AND type.exact: {}'.format(case_type)

    @staticmethod
    def _case_list_url_params(query, owner_id):
        params = {}
        params.update(EMWF.for_user(owner_id))  # Get user slug for Users or Groups Filter
        params.update({'search_query': query})
        return params

    @property
    def _case_list_base_url(self):
        return absolute_reverse('project_report_dispatcher', args=(self.domain, 'case_list'))

    def _case_list_url(self, query, owner_id):
        params = WorkerActivityReport._case_list_url_params(query, owner_id)
        return self._make_url(self._case_list_base_url, params)

    def _case_list_url_cases_opened_by(self, owner_id):
        return self._case_list_url_cases_by(owner_id, is_closed=False)

    def _case_list_url_cases_closed_by(self, owner_id):
        return self._case_list_url_cases_by(owner_id, is_closed=True)

    def _case_list_url_cases_by(self, owner_id, is_closed=False):
        start_date, end_date = self._dates_for_linked_reports(self.datespan, case_list=True)
        prefix = 'closed' if is_closed else 'opened'

        query = "{prefix}_by: {owner_id} AND {prefix}_on: [{start_date} TO {end_date}] {case_query}".format(
            prefix=prefix,
            owner_id=owner_id,
            start_date=start_date,
            end_date=end_date,
            case_query=self._case_query(self.case_type),
        )

        return self._case_list_url(query, owner_id)

    def _case_list_url_total_cases(self, owner_id):
        start_date, end_date = self._dates_for_linked_reports(self.datespan, case_list=True)
        # Subtract a day for inclusiveness
        start_date = (self.datespan.startdate - datetime.timedelta(days=1)).strftime(self.datespan.format)

        query = 'opened_on: [* TO {end_date}] AND NOT closed_on: [* TO {start_date}]'.format(
            end_date=end_date,
            start_date=start_date,
        )
        return self._case_list_url(query, owner_id)

    def _case_list_url_active_cases(self, owner_id):
        start_date, end_date = self._dates_for_linked_reports(self.datespan, case_list=True)
        query = "modified_on: [{start_date} TO {end_date}]".format(
            start_date=start_date,
            end_date=end_date
        )
        return self._case_list_url(query, owner_id)

    def _group_cell(self, group_id, group_name):
        """
        takes group info, and creates a cell that links to the user status report focused on the group
        """
        base_url = absolute_reverse('project_report_dispatcher', args=(self.domain, 'worker_activity'))
        start_date, end_date = self._dates_for_linked_reports(self.datespan)
        params = {
            "group": group_id,
            "startdate": start_date,
            "enddate": end_date,
        }

        url = self._make_url(base_url, params)

        return util.format_datatables_data(
            self._html_anchor_tag(url, group_name),
            group_name,
        )

    def _rows_by_group(self, report_data):
        rows = []
        active_users_by_group = {
            g: len(filter(lambda u: report_data.submissions_by_user.get(u['user_id']), users))
            for g, users in self.users_by_group.iteritems()
        }

        for group, users in self.users_by_group.iteritems():
            group_name, group_id = tuple(group.split('|'))
            if group_name == 'no_group':
                continue

            case_sharing_groups = set(reduce(operator.add, [u['group_ids'] + [u['location_id']] for u in users], []))
            active_cases = sum([int(report_data.active_cases_by_owner.get(u["user_id"].lower(), 0)) for u in users]) + \
                sum([int(report_data.active_cases_by_owner.get(g_id, 0)) for g_id in case_sharing_groups])
            total_cases = sum([int(report_data.total_cases_by_owner.get(u["user_id"].lower(), 0)) for u in users]) + \
                sum([int(report_data.total_cases_by_owner.get(g_id, 0)) for g_id in case_sharing_groups])
            active_users = int(active_users_by_group.get(group, 0))
            total_users = len(self.users_by_group.get(group, []))

            rows.append([
                # Group Name
                self._group_cell(group_id, group_name),
                # Forms Submitted
                self._submit_history_link(
                    group_id,
                    sum([int(report_data.submissions_by_user.get(user["user_id"], 0)) for user in users]),
                ),
                # Avg forms submitted
                util.numcell(
                    sum(
                        [int(report_data.avg_submissions_by_user.get(user["user_id"], 0))
                        for user in users]
                    ) / self.num_avg_intervals
                ),
                # Active users
                util.numcell("%s / %s" % (active_users, total_users),
                             value=int((float(active_users) / total_users) * 10000) if total_users else -1,
                             raw="%s / %s" % (active_users, total_users)),
                # Cases opened
                util.numcell(
                    sum(
                        [int(report_data.cases_opened_by_user.get(user["user_id"].lower(), 0))
                        for user in users]
                    )
                ),
                # Cases closed
                util.numcell(
                    sum(
                        [int(report_data.cases_closed_by_user.get(user["user_id"].lower(), 0))
                        for user in users]
                    )
                ),
                # Active cases
                util.numcell(active_cases),
                # Total Cases
                util.numcell(total_cases),
                # Percent active cases
                util.numcell(
                    (float(active_cases) / total_cases) * 100 if total_cases else 'nan', convert='float'
                ),
            ])
        return rows

    def _rows_by_user(self, report_data):
        rows = []
        last_form_by_user = self.es_last_submissions()
        for user in self.users_to_iterate:
            active_cases = int(report_data.active_cases_by_owner.get(user["user_id"].lower(), 0)) + \
                sum([int(report_data.active_cases_by_owner.get(group_id, 0)) for group_id in user["group_ids"]]) + \
                int(report_data.active_cases_by_owner.get(user["location_id"], 0))
            total_cases = int(report_data.total_cases_by_owner.get(user["user_id"].lower(), 0)) + \
                sum([int(report_data.total_cases_by_owner.get(group_id, 0)) for group_id in user["group_ids"]]) + \
                int(report_data.total_cases_by_owner.get(user["location_id"], 0))

            cases_opened = int(report_data.cases_opened_by_user.get(user["user_id"].lower(), 0))
            cases_closed = int(report_data.cases_closed_by_user.get(user["user_id"].lower(), 0))

            if today_or_tomorrow(self.datespan.enddate):
                active_cases_cell = util.numcell(
                    self._html_anchor_tag(self._case_list_url_active_cases(user['user_id']), active_cases),
                    active_cases,
                )
            else:
                active_cases_cell = util.numcell(active_cases)

            rows.append([
                # Username
                user["username_in_report"],
                # Forms Submitted
                self._submit_history_link(
                    user['user_id'],
                    report_data.submissions_by_user.get(user["user_id"], 0),
                ),
                # Average Forms submitted
                util.numcell(
                    int(report_data.avg_submissions_by_user.get(user["user_id"], 0)) / self.num_avg_intervals
                ),
                # Last Form submission
                last_form_by_user.get(user["user_id"]) or _(self.NO_FORMS_TEXT),
                # Cases opened
                util.numcell(
                    self._html_anchor_tag(self._case_list_url_cases_opened_by(user['user_id']), cases_opened),
                    cases_opened,
                ),
                # Cases Closed
                util.numcell(
                    self._html_anchor_tag(self._case_list_url_cases_closed_by(user['user_id']), cases_closed),
                    cases_closed,
                ),
                # Active Cases
                active_cases_cell,
                # Total Cases
                util.numcell(
                    self._html_anchor_tag(self._case_list_url_total_cases(user['user_id']), total_cases),
                    total_cases,
                ),
                # Percent active
                util.numcell(
                    (float(active_cases) / total_cases) * 100 if total_cases else 'nan', convert='float'
                ),

            ])

        return rows

    def _report_data(self):
        # Adjust to be have inclusive dates
        duration = (self.datespan.enddate - self.datespan.startdate) + datetime.timedelta(days=1)
        avg_datespan = DateSpan(self.datespan.startdate - (duration * self.num_avg_intervals),
                                self.datespan.startdate - datetime.timedelta(days=1))

        if avg_datespan.startdate.year < 1900:  # srftime() doesn't work for dates below 1900
            avg_datespan.startdate = datetime.datetime(1900, 1, 1)

        return WorkerActivityReportData(
            avg_submissions_by_user=get_submission_counts_by_user(self.domain, avg_datespan),
            submissions_by_user=get_submission_counts_by_user(self.domain, self.datespan),
            active_cases_by_owner=get_active_case_counts_by_owner(self.domain, self.datespan, self.case_types),
            total_cases_by_owner=get_total_case_counts_by_owner(self.domain, self.datespan, self.case_types),
            cases_closed_by_user=get_case_counts_closed_by_user(self.domain, self.datespan, self.case_types),
            cases_opened_by_user=get_case_counts_opened_by_user(self.domain, self.datespan, self.case_types),
        )

    def _total_row(self, rows, report_data):
        total_row = [_("Total")]
        summing_cols = [1, 2, 4, 5]

        for col in range(1, len(self.headers)):
            if col in summing_cols:
                total_row.append(
                    sum(filter(lambda x: not math.isnan(x), [row[col].get('sort_key', 0) for row in rows]))
                )
            else:
                total_row.append('---')
        num = len(filter(lambda row: row[3] != _(self.NO_FORMS_TEXT), rows))
        case_owners = set()
        for user in self.users_to_iterate:
            case_owners = case_owners.union((user.user_id, user.location_id))
            case_owners = case_owners.union(user.group_ids)
        total_row[6] = sum(
            [int(report_data.active_cases_by_owner.get(id, 0))
             for id in case_owners])
        total_row[7] = sum(
            [int(report_data.total_cases_by_owner.get(id, 0))
             for id in case_owners])
        if self.view_by_groups:
            active_users = set()
            all_users = set()
            for users in self.users_by_group.values():
                for user in users:
                    if report_data.submissions_by_user.get(user['user_id'], False):
                        active_users.add(user['user_id'])
                    all_users.add(user['user_id'])
            total_row[3] = '%s / %s' % (len(active_users), len(all_users))
        else:
            total_row[3] = '%s / %s' % (num, len(rows))
        return total_row

    @property
    def rows(self):
        report_data = self._report_data()

        rows = []
        if self.view_by_groups:
            rows = self._rows_by_group(report_data)
        else:
            rows = self._rows_by_user(report_data)

        self.total_row = self._total_row(rows, report_data)
        return rows
