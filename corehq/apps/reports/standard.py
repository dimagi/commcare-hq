from _collections import defaultdict
import datetime
import json
import logging
import sys
from StringIO import StringIO
import dateutil
from corehq.apps.groups.models import Group
from corehq.apps.users.models import CommCareUser
from couchexport.export import export_from_tables
from couchexport.shortcuts import export_response
from dimagi.utils.decorators.memoized import memoized
from django.conf import settings
from django.core.urlresolvers import reverse, NoReverseMatch
from django.http import HttpResponseBadRequest, Http404, HttpResponse
from django.template.defaultfilters import yesno
from django.utils import html
import pytz
from restkit.errors import RequestFailed
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.models import Application, get_app
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports import util
from corehq.apps.reports.calc import entrytimes
from corehq.apps.reports.custom import HQReport
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.display import xmlns_to_name, FormType
from corehq.apps.reports.fields import FilterUsersField, CaseTypeField, SelectMobileWorkerField, SelectOpenCloseField, SelectApplicationField
from corehq.apps.reports.models import HQUserType, FormExportSchema
from couchexport.models import SavedExportSchema
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import DatatablesParams, CouchFilter, FilteredPaginator
from dimagi.utils.dates import DateSpan, force_to_datetime
from dimagi.utils.parsing import json_format_datetime, string_to_datetime
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import json_request, get_url_base

DATE_FORMAT = "%Y-%m-%d"
user_link_template = '<a href="%(link)s?individual=%(user_id)s">%(username)s</a>'


class StandardHQReport(HQReport):
    user_filter = HQUserType.use_defaults()
    fields = ['corehq.apps.reports.fields.FilterUsersField']
    history = None
    use_json = False
    hide_filters = False
    custom_breadcrumbs = None
    base_slug = 'reports'
    asynchronous = True


    def process_basic(self):
        self.request_params = json_request(self.request.GET)
        self.individual = self.request_params.get('individual', '')
        self.user_filter, _ = FilterUsersField.get_user_filter(self.request)
        self.group = self.request_params.get('group','')
        self.users = util.get_all_users_by_domain(self.domain, self.group, self.individual, self.user_filter)
        if not self.fields:
            self.hide_filters = True

        if self.individual and self.users:
            self.name = "%s for %s" % (self.name, self.users[0].raw_username)
        if self.show_time_notice:
            self.context.update(
                timezone_now = datetime.datetime.now(tz=self.timezone),
                timezone = self.timezone.zone
            )

        self.context.update(
            standard_report = True,
            layout_flush_content = True,
            report_hide_filters = self.hide_filters,
            report_breadcrumbs = self.custom_breadcrumbs,
            base_slug = self.base_slug
        )

    def get_global_params(self):
        self.process_basic()
        # the history param lets you run a report as if it were a given time in the past
        hist_param = self.request_params.get('history', None)
        if hist_param:
            self.history = datetime.datetime.strptime(hist_param, DATE_FORMAT)

        self.case_type = self.request_params.get('case_type', '')

        try:
            self.group = Group.get(self.group) if self.group else ''
        except Exception:
            pass

        self.get_parameters()

    def get_parameters(self):
        # here's where you can define any extra parameters you want to process before
        # proceeding with the rest of get_report_context
        pass

    def get_report_context(self):
        self.build_selector_form()
        self.context.update(util.report_context(self.domain,
                                        report_partial = self.report_partial,
                                        title = self.name,
                                        headers = self.headers,
                                        rows = self.rows,
                                        show_time_notice = self.show_time_notice
                                      ))
    
    def as_view(self):
        if self.asynchronous:
            self.process_basic()
        else:
            self.get_global_params()
        return super(StandardHQReport, self).as_view()

    def as_async(self, static_only=False):
        self.get_global_params()
        return super(StandardHQReport, self).as_async(static_only=static_only)

    def as_json(self):
        self.get_global_params()
        return super(StandardHQReport, self).as_json()

    @classmethod
    def get_user_link(cls, domain, user):
        user_link = user_link_template % {"link": "%s%s" % (get_url_base(), reverse("report_dispatcher", args=[domain, CaseListReport.slug])),
                               "user_id": user.user_id,
                               "username": user.username_in_report}
        return user_link

class StandardTabularHQReport(StandardHQReport):
    total_row = None
    default_rows = 10
    start_at_row = 0
    fix_left_col = False
    fix_cols = dict(num=1, width=200)

    exportable = True

    def get_headers(self):
        return DataTablesHeader()

    def get_rows(self):
        return self.rows

    def get_report_context(self):
        self.context['report_datatables'] = {
            "defaultNumRows": self.default_rows,
            "startAtRowNum": self.start_at_row
        }
        if self.use_json:
            self.context['ajax_source'] = reverse('json_report_dispatcher',
                                                  args=[self.domain, self.slug])
            self.context['ajax_params'] = [dict(name='individual', value=self.individual),
                           dict(name='group', value=self.group),
                           dict(name='case_type', value=self.case_type),
                           dict(name='ufilter', value=[f.type for f in self.user_filter if f.show])]

        self.headers = self.get_headers()
        self.rows = self.get_rows()

        self.context['header'] = self.headers
        self.context['rows'] = self.rows
        if self.total_row:
            self.context['total_row'] = self.total_row

        super(StandardTabularHQReport, self).get_report_context()
        if self.fix_left_col:
            self.context['report']['fixed_cols'] = self.fix_cols

    def as_export(self):
        self.get_global_params()
        self.get_report_context()
        self.calc()
        try:
            import xlwt
        except ImportError:
            raise Exception("It doesn't look like this machine is configured for "
                        "excel export. To export to excel you have to run the "
                        "command:  easy_install xlutils")
        headers = self.get_headers()
        html_rows = self.get_rows()

        table = headers.as_table
        rows = []
        for row in html_rows:
            row = [col.get("sort_key", col) if isinstance(col, dict) else col for col in row]
            rows.append(row)
        table.extend(rows)
        if self.total_row:
            total_row = [col.get("sort_key", col) if isinstance(col, dict) else col for col in self.total_row]
            table.append(total_row)

        table_format = [[self.name, table]]

        temp = StringIO()
        export_from_tables(table_format, temp, "xls")
        return export_response(temp, "xls", self.slug)


class PaginatedHistoryHQReport(StandardTabularHQReport):
    use_json = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']

    count = 0
    _total_count = None
    exportable = False
    
    @property
    def total_count(self):
        if self._total_count is not None:
            return self._total_count
        return self.count
    
    def get_parameters(self):
        self.userIDs = [user.user_id for user in self.users if user.user_id]
        self.usernames = dict([(user.user_id, user.username_in_report) for user in self.users])

    def json_data(self):
        params = DatatablesParams.from_request_dict(self.request.REQUEST)
        rows = self.paginate_rows(params.start, params.count)
        return {
            "sEcho": params.echo,
            "iTotalDisplayRecords": self.count,
            "iTotalRecords": self.total_count,
            "aaData": rows
        }

    def paginate_rows(self, skip, limit):
        # gather paginated rows here
        self.count = 0
        return []


class StandardDateHQReport(StandardHQReport):

    def __init__(self, domain, request, base_context=None):
        base_context = base_context or {}
        super(StandardDateHQReport, self).__init__(domain, request, base_context)
        self.datespan = self.get_default_datespan()
        self.datespan.is_default = True

    def get_default_datespan(self):
        return DateSpan.since(7, format="%Y-%m-%d", timezone=self.timezone)

    def process_basic(self):
        if self.request.datespan.is_valid() and not self.request.datespan.is_default:
            self.datespan.enddate = self.request.datespan.enddate
            self.datespan.startdate = self.request.datespan.startdate
            self.datespan.is_default = False
        self.datespan.timezone = self.timezone
        self.request.datespan = self.datespan
        self.context.update(dict(datespan=self.datespan))
        super(StandardDateHQReport, self).process_basic()

class CaseActivityReport(StandardTabularHQReport):
    """
    User    Last 30 Days    Last 60 Days    Last 90 Days   Active Clients              Inactive Clients
    danny   5 (25%)         10 (50%)        20 (100%)       17                          6
    (name)  (modified_since(x)/[active + closed_since(x)])  (open & modified_since(120)) (open & !modified_since(120))
    """
    name = 'Case Activity'
    slug = 'case_activity'
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.CaseTypeField',
              'corehq.apps.reports.fields.GroupField']
    all_users = None
    display_data = ['percent']


    class Row(object):
        def __init__(self, report, user):
            self.report = report
            self.user = user

        def active_count(self):
            """Open clients seen in the last 120 days"""
            return self.report.get_number_cases(
                user_id=self.user.get_id,
                modified_after=self.report.utc_now - self.report.inactive,
                modified_before=self.report.utc_now,
                closed=False,
            )

        def inactive_count(self):
            """Open clients not seen in the last 120 days"""
            return self.report.get_number_cases(
                user_id=self.user.get_id,
                modified_before=self.report.utc_now - self.report.inactive,
                closed=False,
            )

        def modified_count(self, startdate=None, enddate=None):
            enddate = enddate or self.report.utc_now
            return self.report.get_number_cases(
                user_id=self.user.get_id,
                modified_after=startdate,
                modified_before=enddate,
            )

        def closed_count(self, startdate=None, enddate=None):
            enddate = enddate or self.report.utc_now
            return self.report.get_number_cases(
                user_id=self.user.get_id,
                modified_after=startdate,
                modified_before=enddate,
                closed=True
            )

        def header(self):
            return util.format_datatables_data(StandardHQReport.get_user_link(self.report.domain, self.user),
                    self.user.username_in_report)

    class TotalRow(object):
        def __init__(self, rows, header):
            self.rows = rows
            self._header = header

        def active_count(self):
            return sum([row.active_count() for row in self.rows])

        def inactive_count(self):
            return sum([row.inactive_count() for row in self.rows])

        def modified_count(self, startdate=None, enddate=None):
            return sum([row.modified_count(startdate, enddate) for row in self.rows])

        def closed_count(self, startdate=None, enddate=None):
            return sum([row.closed_count(startdate, enddate) for row in self.rows])

        def header(self):
            return self._header

    def get_parameters(self):
        landmarks_param = self.request_params.get('landmarks', [30,60,90])
        inactive_param = self.request_params.get('inactive', 120)
        self.display_data = self.request_params.get('display', ['percent'])
        if landmarks_param + [inactive_param] != sorted(landmarks_param + [inactive_param]):
            raise Http404()
        self.landmarks = [datetime.timedelta(days=l) for l in landmarks_param]
        self.inactive = datetime.timedelta(days=inactive_param)
        if self.history:
            self.now = self.history
        else:
            self.now = datetime.datetime.now(tz=self.timezone)

    @property
    @memoized
    def utc_now(self):
        return tz_utils.adjust_datetime_to_timezone(self.now, self.timezone.zone, pytz.utc.zone)

    def get_headers(self):
        headers = DataTablesHeader(DataTablesColumn("Users"))
        for landmark in self.landmarks:
            headers.add_column(DataTablesColumn("Last %s Days" % landmark.days if landmark else "Ever",
                        sort_type=DTSortType.NUMERIC,
                        help_text='Number of cases modified (or closed) in the last %s days' % landmark.days))
        headers.add_column(DataTablesColumn("Active Cases",
            sort_type=DTSortType.NUMERIC,
            help_text='Number of cases modified in the last %s days that are still open' % self.inactive.days))
        headers.add_column(DataTablesColumn("Inactive Cases",
            sort_type=DTSortType.NUMERIC,
            help_text="Number of cases that are open but haven't been touched in the last %s days" % self.inactive.days))
        return headers

    def get_rows(self):
        rows = [self.Row(self, user) for user in self.users]
        total_row = self.TotalRow(rows, "All Users")

        def format_row(row):
            cells = [row.header()]
            def add_numeric_cell(text, value=None):
                if value is None:
                    value = int(text)
                cells.append(util.format_datatables_data(text=text, sort_key=value))
            for landmark in self.landmarks:
                value = row.modified_count(self.utc_now - landmark)
                total = row.active_count() + row.closed_count(self.utc_now - landmark)

                try:
                    display = '%d (%d%%)' % (value, value * 100. / total)
                except ZeroDivisionError:
                    display = '%d' % value
                add_numeric_cell(display, value)
            add_numeric_cell(row.active_count())
            add_numeric_cell(row.inactive_count())
            return cells
        self.total_row = format_row(total_row)
        return map(format_row, rows)

    def get_number_cases(self, user_id, modified_after=None, modified_before=None, closed=None):
        key = [self.domain, {} if closed is None else closed, self.case_type or {}, user_id]

        if modified_after is None:
            start = ""
        else:
            start = json_format_datetime(modified_after)

        if modified_before is None:
            end = {}
        else:
            end = json_format_datetime(modified_before)

        return get_db().view('case/by_date_modified',
            startkey=key + [start],
            endkey=key + [end],
            group=True,
            group_level=0,
            wrapper=lambda row: row['value']
        ).one() or 0

class DailyReport(StandardDateHQReport, StandardTabularHQReport):
    couch_view = ''
    fix_left_col = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    def get_headers(self):
        self.dates = [self.datespan.startdate]
        while self.dates[-1] < self.datespan.enddate:
            self.dates.append(self.dates[-1] + datetime.timedelta(days=1))

        headers = DataTablesHeader(DataTablesColumn("Username", span=3))
        for d in self.dates:
            headers.add_column(DataTablesColumn(d.strftime(DATE_FORMAT), sort_type=DTSortType.NUMERIC))
        headers.add_column(DataTablesColumn("Total", sort_type=DTSortType.NUMERIC))
        return headers

    def get_rows(self):
        utc_dates = [tz_utils.adjust_datetime_to_timezone(date, self.timezone.zone, pytz.utc.zone) for date in self.dates]
        date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(utc_dates)])

        key = [self.domain]
        results = get_db().view(
            self.couch_view,
            reduce=False,
            startkey=key+[self.datespan.startdate_param_utc],
            endkey=key+[self.datespan.enddate_param_utc]
        ).all()

        user_map = dict([(user.user_id, i) for (i, user) in enumerate(self.users)])
        userIDs = [user.user_id for user in self.users]
        rows = [[0]*(2+len(date_map)) for _ in range(len(self.users))]
        total_row = [0]*(2+len(date_map))

        for result in results:
            _, date = result['key']
            date = dateutil.parser.parse(date)
            tz_offset = self.timezone.localize(self.datespan.enddate).strftime("%z")
            date = date + datetime.timedelta(hours=int(tz_offset[0:3]), minutes=int(tz_offset[0]+tz_offset[3:5]))
            date = date.isoformat()
            val = result['value']
            user_id = val.get("user_id")
            if user_id in userIDs:
                date_key = date_map.get(date[0:10], None)
                if date_key:
                    rows[user_map[user_id]][date_key] += 1

        for i, user in enumerate(self.users):
            rows[i][0] = StandardHQReport.get_user_link(self.domain, user)
            total = sum(rows[i][1:-1])
            rows[i][-1] = total
            total_row[1:-1] = [total_row[ind+1]+val for ind, val in enumerate(rows[i][1:-1])]
            total_row[-1] += total

        total_row[0] = "All Users"
        self.total_row = total_row

        for row in rows:
            row[1:] = [util.format_datatables_data(val, val) for val in row[1:]]

        return rows

class DailySubmissionsReport(DailyReport):
    name = "Daily Form Submissions"
    slug = "daily_submissions"
    couch_view = 'reports/daily_submissions'

class DailyFormCompletionsReport(DailyReport):
    name = "Daily Form Completions"
    slug = "daily_completions"
    couch_view = 'reports/daily_completions'

class SubmissionsByFormReport(StandardTabularHQReport, StandardDateHQReport):
    name = "Submissions By Form"
    slug = "submissions_by_form"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']
    fix_left_col = True

    def get_parameters(self):
        self.form_types = self.get_relevant_form_types()

    def get_headers(self):
        form_names = [xmlns_to_name(*id_tuple) for id_tuple in self.form_types]
        form_names = [name.replace("/", " / ") if name is not None else '(No name)' for name in form_names]

        if self.form_types:
            # this fails if form_names, form_types is [], []
            form_names, self.form_types = zip(*sorted(zip(form_names, self.form_types)))

        headers = DataTablesHeader(DataTablesColumn("User", span=3))
        for name in list(form_names):
            headers.add_column(DataTablesColumn(name, sort_type=DTSortType.NUMERIC))
        headers.add_column(DataTablesColumn("All Forms", sort_type=DTSortType.NUMERIC))

        return headers

    def get_rows(self):
        counts = self.get_submissions_by_form_json()
        rows = []
        totals_by_form = defaultdict(int)

        for user in self.users:
            row = []
            for form_type in self.form_types:
                userID = user.userID
                try:
                    count = counts[userID][form_type]
                    row.append(count)
                    totals_by_form[form_type] += count
                except Exception:
                    row.append(0)
            row_sum = sum(row)
            rows.append([StandardHQReport.get_user_link(self.domain, user)] + [util.format_datatables_data(row_data, row_data) for row_data in row] + [util.format_datatables_data("<strong>%s</strong>" % row_sum, row_sum)])

        totals_by_form = [totals_by_form[form_type] for form_type in self.form_types]
        self.total_row = ["All Users"] + ["%s" % t for t in totals_by_form] + ["<strong>%s</strong>" % sum(totals_by_form)]

        return rows

    def get_submissions_by_form_json(self):
        userIDs = [user.user_id for user in self.users]
        self.datespan.startdate_param
        self.datespan.enddate_param
        submissions = XFormInstance.view('reports/all_submissions',
            startkey=[self.domain, self.datespan.startdate_param_utc],
            endkey=[self.domain, self.datespan.enddate_param_utc],
            include_docs=True,
            reduce=False
        )
        counts = defaultdict(lambda: defaultdict(int))
        for sub in submissions:
            try:
                app_id = sub['app_id']
            except Exception:
                app_id = None
            try:
                userID = sub['form']['meta']['userID']
            except Exception:
                # if a form don't even have a userID, don't even bother tryin'
                pass
            else:
                if (userIDs is None) or (userID in userIDs):
                    counts[userID][FormType(self.domain, sub['xmlns'], app_id).get_id_tuple()] += 1
        return counts

    def get_relevant_form_types(self):
        userIDs = [user.user_id for user in self.users]
        submissions = XFormInstance.view('reports/all_submissions',
            startkey=[self.domain, self.datespan.startdate_param_utc],
            endkey=[self.domain, self.datespan.enddate_param_utc],
            include_docs=True,
            reduce=False
        )
        form_types = set()

        for submission in submissions:
            try:
                xmlns = submission['xmlns']
            except KeyError:
                xmlns = None

            try:
                app_id = submission['app_id']
            except Exception:
                app_id = None

            if userIDs is not None:
                try:
                    userID = submission['form']['meta']['userID']
                except Exception:
                    pass
                else:
                    if userID in userIDs:
                        form_types.add(FormType(self.domain, xmlns, app_id).get_id_tuple())
            else:
                form_types.add(FormType(self.domain, xmlns, app_id).get_id_tuple())

        return sorted(form_types)

class FormCompletionTrendsReport(StandardTabularHQReport, StandardDateHQReport):
    name = "Form Completion Trends"
    slug = "completion_times"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectFormField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    def get_headers(self):
        return DataTablesHeader(DataTablesColumn("User"),
                                DataTablesColumn("Average duration"),
                                DataTablesColumn("Shortest"),
                                DataTablesColumn("Longest"),
                                DataTablesColumn("No. of Forms"))

    def get_rows(self):
        form = self.request_params.get('form', '')
        rows = []

        if form:
            totalsum = totalcount = 0
            def to_minutes(val_in_ms, d=None):
                if val_in_ms is None or d == 0:
                    return None
                elif d:
                    val_in_ms /= d
                return datetime.timedelta(seconds=int((val_in_ms + 500)/1000))

            globalmin = sys.maxint
            globalmax = 0
            for user in self.users:
                datadict = entrytimes.get_user_data(self.domain, user.user_id, form, self.datespan)
                rows.append([StandardHQReport.get_user_link(self.domain, user),
                             to_minutes(float(datadict["sum"]), float(datadict["count"])),
                             to_minutes(datadict["min"]),
                             to_minutes(datadict["max"]),
                             datadict["count"]
                             ])
                totalsum = totalsum + datadict["sum"]
                totalcount = totalcount + datadict["count"]
                if datadict['min'] is not None:
                    globalmin = min(globalmin, datadict["min"])
                if datadict['max'] is not None:
                    globalmax = max(globalmax, datadict["max"])
            if totalcount:
                self.total_row = ["Total",
                                    to_minutes(float(totalsum), float(totalcount)),
                                    to_minutes(globalmin),
                                    to_minutes(globalmax),
                                    totalcount]
        return rows


class SubmitHistory(PaginatedHistoryHQReport):
    name = 'Submit History'
    slug = 'submit_history'

    def get_headers(self):
        headers = DataTablesHeader(DataTablesColumn("View Form"),
            DataTablesColumn("Username"),
            DataTablesColumn("Submit Time"),
            DataTablesColumn("Form"))
        headers.no_sort = True
        return headers

    def paginate_rows(self, skip, limit):
        rows = []
        all_hist = HQFormData.objects.filter(userID__in=self.userIDs, domain=self.domain)
        self.count = all_hist.count()
        history = all_hist.extra(order_by=['-received_on'])[skip:skip+limit]
        for data in history:
            if data.userID in self.userIDs:
                time = tz_utils.adjust_datetime_to_timezone(data.received_on, pytz.utc.zone, self.timezone.zone)
                time = time.strftime("%Y-%m-%d %H:%M:%S")
                xmlns = data.xmlns
                app_id = data.app_id
                xmlns = xmlns_to_name(self.domain, xmlns, app_id=app_id)
                rows.append([self.form_data_link(data.instanceID), self.usernames[data.userID], time, xmlns])

        return rows

    def form_data_link(self, instance_id):
        return "<a class='ajax_dialog' href='%s'>View Form</a>" % reverse('render_form_data', args=[self.domain, instance_id])





class SubmissionTimesReport(StandardHQReport):
    name = "Submission Times"
    slug = "submit_time_punchcard"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']
    template_name = "reports/async/basic.html"
    report_partial = "reports/partials/punchcard.html"
    show_time_notice = True

    def calc(self):
        data = defaultdict(lambda: 0)
        for user in self.users:
            startkey = [self.domain, user.user_id]
            endkey = [self.domain, user.user_id, {}]
            view = get_db().view("formtrends/form_time_by_user",
                                 startkey=startkey,
                                 endkey=endkey,
                                 group=True)
            for row in view:
                domain, _user, day, hour = row["key"]

                if hour and day:
                    #adjust to timezone
                    now = datetime.datetime.utcnow()
                    hour = int(hour)
                    day = int(day)
                    report_time = datetime.datetime(now.year, now.month, now.day, hour, tzinfo=pytz.utc)
                    report_time = tz_utils.adjust_datetime_to_timezone(report_time, pytz.utc.zone, self.timezone.zone)
                    hour = report_time.hour

                    data["%d %02d" % (day, hour)] = data["%d %02d" % (day, hour)] + row["value"]
        self.context["chart_url"] = self.generate_chart(data)

    @classmethod
    def generate_chart(cls, data, width=950, height=300):
        """
        Gets a github style punchcard chart.

        Hat tip: http://github.com/dustin/bindir/blob/master/gitaggregates.py
        """
        no_data = not data
        try:
            from pygooglechart import ScatterChart
        except ImportError:
            raise Exception("""Aw shucks, someone forgot to install the google chart library
on this machine and the report needs it. To get it, run
easy_install pygooglechart.  Until you do that this won't work.
""")

        chart = ScatterChart(width, height, x_range=(-1, 24), y_range=(-1, 7))

        chart.add_data([(h % 24) for h in range(24 * 8)])

        d=[]
        for i in range(8):
            d.extend([i] * 24)
        chart.add_data(d)

        day_names = "Sun Mon Tue Wed Thu Fri Sat".split(" ")
        days = (0, 6, 5, 4, 3, 2, 1)

        sizes=[]
        for d in days:
            sizes.extend([data["%d %02d" % (d, h)] for h in range(24)])
        sizes.extend([0] * 24)
        if no_data:
            # fill in a line out of view so that chart.get_url() doesn't crash
            sizes.extend([1] * 24)
        chart.add_data(sizes)

        chart.set_axis_labels('x', [''] + [str(h) for h  in range(24)] + [''])
        chart.set_axis_labels('y', [''] + [day_names[n] for n in days] + [''])

        chart.add_marker(1, 1.0, 'o', '333333', 25)
        return chart.get_url() + '&chds=-1,24,-1,7,0,20'

class SubmitDistributionReport(StandardHQReport):
    name = "Submit Distribution"
    slug = "submit_distribution"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']
    template_name = "reports/async/basic.html"
    report_partial = "reports/partials/generic_piechart.html"

    def calc(self):
        predata = {}
        data = []
        for user in self.users:
            startkey = ["u", self.domain, user.user_id]
            endkey = ["u", self.domain, user.user_id, {}]
            view = get_db().view("formtrends/form_type_by_user",
                                 startkey=startkey,
                                 endkey=endkey,
                                 group=True,
                                 reduce=True)
            for row in view:
                xmlns = row["key"][-1]
                form_name = xmlns_to_name(self.domain, xmlns, app_id=None)
                if form_name in predata:
                    predata[form_name]["value"] = predata[form_name]["value"] + row["value"]
                    predata[form_name]["description"] = "(%s) submissions of %s" % \
                                                        (predata[form_name]["value"], form_name)
                else:
                    predata[form_name] = {"display": form_name,
                                            "value": row["value"],
                                            "description": "(%s) submissions of %s" % \
                                                            (row["value"], form_name)}
        for value in predata.values():
            data.append(value)

        self.context.update({
            "chart_data": data,
            "user_id": self.individual,
            "graph_width": 900,
            "graph_height": 500
        })

class MapReport(StandardHQReport):

    """
HOW TO CONFIGURE THIS REPORT

create a couch doc as such:

{
  "doc_type": "MapsReportConfig",
  "domain": <domain>,
  "config": {
    "case_types": [
      // for each case type

      {
        "case_type": <commcare case type>,
        "display_name": <display name of case type>,

        // either of the following two fields
        "geo_field": <case property for a geopoint question>,
        "geo_linked_to": <geo-enabled case type that this case links to>,

        "fields": [
          // for each reportable field

          "field": <case property>, // or one of the following magic values:
                 // "_count" -- report on the number of cases of this type
          "display_name": <display name for field>,
          "type": <datatype for field>, // can be "numeric", "enum", or "num_discrete" (enum with numeric values)

          // if type is "numeric" or "num_discrete"
          // these control the rendering of numeric data points (all are optional)
          "scale": <N>, // if absent, scale is calculated dynamically based on the max value in the field
          "color": <css color>,

          // if type is "enum" or "num_discrete" (optional, but recommended)
          "values": [
            // for each multiple-choice value

            {
              "value": <data value>,
              "label": <display name>, //optional
              "color": <css color>, //optional
            },
          ]
        ]
      },
    ]
  }
}
"""

    name = "Maps"
    slug = "maps"
    fields = [] # todo: support some of these filters -- right now this report
                # is more of a playground, so all the filtering is done in its
                # own ajax sidebar
    template_name = "reports/async/basic.html"
    report_partial = "reports/partials/maps.html"
    asynchronous = False

    def calc(self):
        self.context['maps_api_key'] = settings.GMAPS_API_KEY
        self.context['case_api_url'] = reverse('cloudcare_get_cases', kwargs={'domain': self.domain})

        config = get_db().view('reports/maps_config', key=[self.domain], include_docs=True).one()
        if config:
            config = config['doc']['config']
        self.context['config'] = json.dumps(config)

class SubmitTrendsReport(StandardDateHQReport):
    #nuked until further notice
    name = "Submit Trends"
    slug = "submit_trends"
    fields = ['corehq.apps.reports.fields.SelectMobileWorkerField',
              'corehq.apps.reports.fields.DatespanField']
    template_name = "reports/async/basic.html"
    report_partial = "reports/partials/formtrends.html"

    def calc(self):
        self.context.update({
            "user_id": self.individual,
        })

class ExcelExportReport(StandardDateHQReport):
    name = "Export Submissions to Excel"
    slug = "excel_export_data"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']
    template_name = "reports/reportdata/excel_export_data.html"

    def get_default_datespan(self):
        datespan = super(ExcelExportReport, self).get_default_datespan()
        def extract_date(x):
            try:
                def clip_timezone(datestring):
                    return datestring[:len('yyyy-mm-ddThh:mm:ss')]
                return string_to_datetime(clip_timezone(x['key'][1]))
            except Exception:
                logging.error("Tried to get a date from this, but it didn't work: %r" % x)
                return None
        startdate = get_db().view('reports/all_submissions',
            startkey=[self.domain],
            endkey=[self.domain,{}],
            limit=1,
            descending=False,
            reduce=False,
            wrapper=extract_date
        ).one()
        if startdate:
            datespan.startdate = startdate
        return datespan

    def calc(self):
        # This map for this view emits twice, once with app_id and once with {}, letting you join across all app_ids.
        # However, we want to separate out by (app_id, xmlns) pair not just xmlns so we use [domain] to [domain, {}]
        forms = []
        unknown_forms = []
        for f in get_db().view('reports/forms_by_xmlns', startkey=[self.domain], endkey=[self.domain, {}], group=True):
            form = f['value']
            if form.get('app_deleted') and not form.get('submissions'):
                continue
            if 'app' in form:
                form['has_app'] = True
            else:
                app_id = f['key'][1] or ''
                form['app'] = {
                    'id': app_id
                }
                form['has_app'] = False
                form['show_xmlns'] = True
                unknown_forms.append(form)

            form['current_app'] = form.get('app')
            forms.append(form)

        if unknown_forms:
            apps = get_db().view('reports/forms_by_xmlns',
                startkey=['^Application', self.domain],
                endkey=['^Application', self.domain, {}],
                reduce=False,
            )
            possibilities = defaultdict(list)
            for app in apps:
                # index by xmlns
                x = app['value']
                x['has_app'] = True
                possibilities[app['key'][2]].append(x)

            class AppCache(dict):
                def __init__(self, domain):
                    super(AppCache, self).__init__()
                    self.domain = domain

                def __getitem__(self, item):
                    if not self.has_key(item):
                        try:
                            self[item] = get_app(app_id=item, domain=self.domain)
                        except Http404:
                            pass
                    return super(AppCache, self).__getitem__(item)

            app_cache = AppCache(self.domain)

            for form in unknown_forms:
                app = None
                if form['app']['id']:
                    try:
                        app = app_cache[form['app']['id']]
                        form['has_app'] = True
                    except KeyError:
                        form['app_does_not_exist'] = True
                        form['possibilities'] = possibilities[form['xmlns']]
                        if form['possibilities']:
                            form['duplicate'] = True
                    else:
                        if app.domain != self.domain:
                            logging.error("submission tagged with app from wrong domain: %s" % app.get_id)
                        else:
                            if app.copy_of:
                                try:
                                    app = app_cache[app.copy_of]
                                    form['app_copy'] = {'id': app.get_id, 'name': app.name}
                                except KeyError:
                                    form['app_copy'] = {'id': app.copy_of, 'name': '?'}
                            if app.is_deleted():
                                form['app_deleted'] = {'id': app.get_id}
                            try:
                                app_forms = app.get_xmlns_map()[form['xmlns']]
                            except AttributeError:
                                # it's a remote app
                                app_forms = None
                            if app_forms:
                                app_form = app_forms[0]
                                if app_form.doc_type == 'UserRegistrationForm':
                                    form['is_user_registration'] = True
                                else:
                                    app_module = app_form.get_module()
                                    form['module'] = app_module
                                    form['form'] = app_form
                                form['show_xmlns'] = False

                            if not form.get('app_copy') and not form.get('app_deleted'):
                                form['no_suggestions'] = True
                    if app:
                        form['app'] = {'id': app.get_id, 'name': app.name, 'langs': app.langs}

                else:
                    form['possibilities'] = possibilities[form['xmlns']]
                    if form['possibilities']:
                        form['duplicate'] = True
                    else:
                        form['no_suggestions'] = True

        # add saved exports. because of the way in which the key is stored
        # (serialized json) this is a little bit hacky, but works.
        startkey = json.dumps([self.domain, ""])[:-3]
        endkey = "%s{" % startkey
        exports = FormExportSchema.view("couchexport/saved_export_schemas",
            startkey=startkey, endkey=endkey,
            include_docs=True)

        exports = filter(lambda x: x.type == "form", exports)

        forms = sorted(forms, key=lambda form:\
            (0 if not form.get('app_deleted') else 1,
                form['app']['name'],
                form['app']['id'],
                form.get('module', {'id': -1 if form.get('is_user_registration') else 1000})['id'], form.get('form', {'id': -1})['id']
            ) if form['has_app'] else\
            (2, form['xmlns'], form['app']['id'])
        )

        self.context.update({
            "forms": forms,
            "saved_exports": exports,
            "edit": self.request.GET.get('edit') == 'true',
            "get_filter_params": self.get_filter_params(),
        })

    def get_filter_params(self):
        params = self.request.GET.copy()
        params['startdate'] = self.datespan.startdate_display
        params['enddate'] = self.datespan.enddate_display
        return params


class CaseExportReport(StandardHQReport):
    name = "Export Cases, Referrals, &amp; Users"
    slug = "case_export"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField']
    template_name = "reports/reportdata/case_export_data.html"

    def calc(self):
        startkey = json.dumps([self.domain, ""])[:-3]
        endkey = "%s{" % startkey
        exports = SavedExportSchema.view("couchexport/saved_export_schemas",
            startkey=startkey, endkey=endkey,
            include_docs=True).all()
        exports = filter(lambda x: x.type == "case", exports)
        self.context['saved_exports'] = exports
        cases = get_db().view("hqcase/types_by_domain", 
                              startkey=[self.domain], 
                              endkey=[self.domain, {}], 
                              reduce=True,
                              group=True,
                              group_level=2).all()
        self.context['case_types'] = [case['key'][1] for case in cases]
        self.context.update({
            "get_filter_params": self.request.GET.copy()
        })

class ApplicationStatusReport(StandardTabularHQReport):
    name = "Application Status"
    slug = "app_status"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.SelectApplicationField']

    def get_headers(self):
        return DataTablesHeader(DataTablesColumn("Username"),
                                DataTablesColumn("Last Seen",sort_type=DTSortType.NUMERIC),
                                DataTablesColumn("CommCare Version"),
                                DataTablesColumn("Application [Deployed Build]"))

    def get_parameters(self):
        self.selected_app = self.request_params.get(SelectApplicationField.slug, '')

    def get_rows(self):
        rows = []
        for user in self.users:
            last_seen = util.format_datatables_data("Never", -1)
            version = "---"
            app_name = "---"
            is_unknown = True

            endkey = [self.domain, user.userID]
            startkey = [self.domain, user.userID, {}]
            data = XFormInstance.view("reports/last_seen_submission",
                startkey=startkey,
                endkey=endkey,
                include_docs=True,
                descending=True,
                reduce=False).first()

            if data:
                last_seen = util.format_relative_date(data.received_on)

                if data.version != '1':
                    build_id = data.version
                else:
                    build_id = "unknown"

                form_data = data.get_form
                try:
                    app_name = form_data['meta']['appVersion']['#text']
                    version = "2.0 Remote"
                except KeyError:
                    try:
                        app = Application.get(data.app_id)
                        is_unknown = False
                        if self.selected_app and self.selected_app != data.app_id:
                            continue
                        version = app.application_version
                        app_name = "%s [%s]" % (app.name, build_id)
                    except Exception:
                        version = "unknown"
                        app_name = "unknown"
            if is_unknown and self.selected_app:
                continue
            row = [user.username_in_report, last_seen, version, app_name]
            rows.append(row)
        return rows


class CaseListFilter(CouchFilter):
    view = "case/all_cases"

    def __init__(self, domain, case_owner=None, case_type=None, open_case=None):

        self.domain = domain

        key = [self.domain]
        prefix = [open_case] if open_case else ["all"]

        if case_type:
            prefix.append("type")
            key = key+[case_type]
        if case_owner:
            prefix.append("owner")
            key = key+[case_owner]

        key = [" ".join(prefix)]+key

        self._kwargs = dict(
            startkey=key,
            endkey=key+[{}],
            reduce=False
        )

    def get_total(self):
        if 'reduce' in self._kwargs:
            self._kwargs['reduce'] = True
        all_records = get_db().view(self.view,
            **self._kwargs).first()
        return all_records.get('value', 0) if all_records else 0

    def get(self, count):
        if 'reduce' in self._kwargs:
            self._kwargs['reduce'] = False
        return get_db().view(self.view,
            include_docs=True,
            limit=count,
            **self._kwargs).all()

class CaseListReport(PaginatedHistoryHQReport):
    name = 'Case List'
    slug = 'case_list'
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectCaseOwnerField',
              'corehq.apps.reports.fields.CaseTypeField']

    def __init__(self, domain, request, base_context = None):
#        self.disable_lucene = bool(request.GET.get('no_lucene', False))
        # this is temporary...sorry!!!
        self.disable_lucene = True
        if not settings.LUCENE_ENABLED or self.disable_lucene:
            self.fields = ['corehq.apps.reports.fields.SelectCaseOwnerField',
                           'corehq.apps.reports.fields.CaseTypeField',
                           'corehq.apps.reports.fields.SelectOpenCloseField']
        super(CaseListReport,self).__init__(domain, request, base_context)

    def get_parameters(self):
        super(CaseListReport, self).get_parameters()
        user = None
        if self.individual:
            try:
                user = CommCareUser.get_by_user_id(self.individual)
                user = user if user.username_in_report else None
            except Exception:
                pass
        self.case_sharing_groups = user.get_case_sharing_groups() if user else []
        if not settings.LUCENE_ENABLED or self.disable_lucene:
            self.user_filter = HQUserType.use_defaults(show_all=True)

    def get_report_context(self):
        self.context.update({"filter": settings.LUCENE_ENABLED })
        super(PaginatedHistoryHQReport, self).get_report_context()
        self.context['ajax_params'].append(dict(name=SelectOpenCloseField.slug, value=self.request.GET.get(SelectOpenCloseField.slug, '')))
        if self.disable_lucene:
            self.context['ajax_params'].append(dict(name='no_lucene', value=self.disable_lucene))

    def get_headers(self):
        headers = DataTablesHeader(DataTablesColumn("Name"),
            DataTablesColumn("User"),
            DataTablesColumn("Created Date"),
            DataTablesColumn("Modified Date"),
            DataTablesColumn("Status"))
        headers.no_sort = True
        if not self.individual:
            self.name = "%s for %s" % (self.name, SelectMobileWorkerField.get_default_text(self.user_filter))
        if not self.case_type:
            headers.prepend_column(DataTablesColumn("Case Type"))
        open, all = CaseTypeField.get_case_counts(self.domain, self.case_type, self.userIDs)
        if all > 0:
            self.name = "%s (%s/%s open)" % (self.name, open, all)
        else:
            self.name = "%s (empty)" % self.name
        return headers

    def paginate_rows(self, skip, limit):
        rows = []
        self.count = 0

        def _compare_cases(x, y):
            x = x.get('key', [])
            y = y.get('key', [])
            try:
                x = x[-1]
                y = y[-1]
            except Exception:
                x = ""
                y = ""
            return cmp(x, y)

        def _format_row(row):
            if "doc" in row:
                case = CommCareCase.wrap(row["doc"])
            elif "id" in row:
                case = CommCareCase.get(row["id"])
            else:
                raise ValueError("Can't construct case object from row result %s" % row)

            if case.domain != self.domain:
                logging.error("case.domain != self.domain; %r and %r, respectively" % (case.domain, self.domain))

            assert(case.domain == self.domain)

            owner_id = case.owner_id if case.owner_id else case.user_id
            owning_group = None
            try:
                owning_group = Group.get(owner_id)
            except Exception:
                pass

            user_id = self.individual if self.individual else owner_id
            case_owner = self.usernames.get(user_id, "Unknown [%s]" % user_id)

            if owning_group and owning_group.name:
                if self.individual:
                    case_owner = '%s <span class="label label-inverse">%s</span>' % (case_owner, owning_group.name)
                else:
                    case_owner = '%s <span class="label label-inverse">Group</span>' % owning_group.name


            return ([] if self.case_type else [case.type]) + [
                self.case_data_link(row['id'], case.name),
                case_owner,
                self.date_to_json(case.opened_on),
                self.date_to_json(case.modified_on),
                yesno(case.closed, "closed,open")
            ]

        if settings.LUCENE_ENABLED and not self.disable_lucene:
            group_owners = self.case_sharing_groups if self.individual else Group.get_case_sharing_groups(self.domain)
            group_owners = [group._id for group in group_owners]
            case_owners = self.userIDs + group_owners


            search_key = self.request_params.get("sSearch", "")
            query = "domain:(%s)" % self.domain
            query = "%s AND owner_id:(%s)" % (query, " OR ".join(case_owners))
            if self.case_type:
                query = "%s AND type:%s" % (query, self.case_type)
            if search_key:
                query = "(%s) AND %s" % (search_key, query)

            results = get_db().search("case/search", q=query,
                handler="_fti/_design",
                limit=limit, skip=skip, sort="\sort_modified")
            try:
                for row in results:
                    row = _format_row(row)
                    if row is not None:
                        rows.append(row)
                self.count = results.total_rows
            except RequestFailed:
                pass
        else:
            is_open = self.request.GET.get(SelectOpenCloseField.slug)
            all_owners = [self.individual]+[group._id for group in self.case_sharing_groups]
            filters = [CaseListFilter(self.domain, case_owner, case_type=self.case_type, open_case=is_open)
                       for case_owner in all_owners]
            paginator = FilteredPaginator(filters, _compare_cases)
            items = paginator.get(skip, limit)
            self.count = paginator.total

            for item in items:
                row = _format_row(item)
                if row is not None:
                    rows.append(row)

        return rows

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%Y-%m-%d %H:%M:%S') if date else ""

    def case_data_link(self, case_id, case_name):
        try:
            return "<a class='ajax_dialog' href='%s'>%s</a>" %\
                   (reverse('case_details', args=[self.domain, case_id]),
                    case_name)
        except NoReverseMatch:
            return "%s (bad ID format)" % case_name
