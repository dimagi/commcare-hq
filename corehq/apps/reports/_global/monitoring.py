from _collections import defaultdict
import datetime
import logging
import dateutil
from django.core.urlresolvers import reverse
from django.http import Http404
from django.conf import settings
import pytz
import sys
from corehq.apps.domain.models import Domain
from corehq.apps.reports import util
from corehq.apps.reports._global import CouchCachedReportMixin, ProjectReportParametersMixin, \
    DatespanMixin, ProjectReport, DATE_FORMAT, cache_report
from corehq.apps.reports.calc import entrytimes
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.apps.reports.display import xmlns_to_name, FormType
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.models import CaseActivityReportCache
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import get_url_base

monitoring_report_cacher = cache_report(refresh_stale=30, cache_timeout=60)

class WorkerMonitoringReportTable(GenericTabularReport, ProjectReport, ProjectReportParametersMixin):
    """
        #todo doc.
    """
    exportable = True

    def get_user_link(self, user):
        user_link_template = '<a href="%(link)s?individual=%(user_id)s">%(username)s</a>'
        from corehq.apps.reports._global.inspect import CaseListReport
        user_link = user_link_template % {"link": "%s%s" % (get_url_base(),
                                                            CaseListReport.get_url(self.domain)),
                                          "user_id": user.user_id,
                                          "username": user.username_in_report}
        return util.format_datatables_data(text=user_link, sort_key=user.raw_username)

    @property
    @monitoring_report_cacher
    def report_context(self):
        return super(WorkerMonitoringReportTable, self).report_context


class WorkerMonitoringChart(ProjectReport, ProjectReportParametersMixin):
    """
        doc.
    """
    #todo doc

    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectMobileWorkerField']
    flush_layout = True
    report_template_path = "reports/async/basic.html"


class CaseActivityReport(WorkerMonitoringReportTable, CouchCachedReportMixin):
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

    _default_landmarks = [30, 60, 90]
    _landmarks = None
    @property
    def landmarks(self):
        if self._landmarks is None:
            landmarks_param = self.request_params.get('landmarks')
            landmarks_param = landmarks_param if isinstance(landmarks_param, list) else []
            landmarks_param = [param for param in landmarks_param if isinstance(param, int)]
            if landmarks_param:
                for landmark in landmarks_param:
                    if landmark not in self.cached_report.landmark_data:
                        self.cached_report.update_landmarks(landmarks=landmarks_param)
                        self.cached_report.save()
                        break
            self._landmarks = landmarks_param if landmarks_param else self._default_landmarks
        return self._landmarks

    _default_milestone = 120
    _milestone = None
    @property
    def milestone(self):
        if self._milestone is None:
            milestone_param = self.request_params.get('milestone')
            milestone_param = milestone_param if isinstance(milestone_param, int) else None
            if milestone_param:
                if milestone_param not in self.cached_report.active_cases or\
                   milestone_param not in self.cached_report.inactive_cases:
                    self.cached_report.update_status(milestone=milestone_param)
                    self.cached_report.save()
            self._milestone = milestone_param if milestone_param else self._default_milestone
        return self._milestone

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn("User"))
        for landmark in self.landmarks:
            headers.add_column(DataTablesColumn("Last %s Days" % landmark if landmark else "Ever",
                sort_type=DTSortType.NUMERIC,
                help_text='Number of cases modified or closed in the last %s days ' % landmark))
        headers.add_column(DataTablesColumn("Active Cases ",
            sort_type=DTSortType.NUMERIC,
            help_text='Number of cases modified in the last %s days that are still open' % self.milestone))
        headers.add_column(DataTablesColumn("Closed Cases ",
            sort_type=DTSortType.NUMERIC,
            help_text='Number of cases closed in the last %s days' % self.milestone))
        headers.add_column(DataTablesColumn("Inactive Cases ",
            sort_type=DTSortType.NUMERIC,
            help_text="Number of cases that are open but haven't been touched in the last %s days" % self.milestone))
        return headers

    @property
    def rows(self):
        rows = []
        # TODO: cleanup...case type should be None, but not sure how that affects other rports
        self._case_type = self.case_type if self.case_type else None

        def _numeric_val(text, value=None):
            if value is None:
                value = int(text)
            return util.format_datatables_data(text=text, sort_key=value)

        def _format_val(value, total):
            try:
                display = '%d (%d%%)' % (value, value * 100. / total)
            except ZeroDivisionError:
                display = '%d' % value
            return display

        case_key =  self.cached_report.case_key(self.case_type)

        landmark_data = [self.cached_report.landmark_data.get(case_key,
                {}).get(self.cached_report.day_key(landmark), {}) for landmark in self.landmarks]
        active_data = self.cached_report.active_cases.get(case_key,
                {}).get(self.cached_report.day_key(self.milestone), {})
        closed_data = self.cached_report.closed_cases.get(case_key,
                {}).get(self.cached_report.day_key(self.milestone), {})
        inactive_data = self.cached_report.inactive_cases.get(case_key,
                {}).get(self.cached_report.day_key(self.milestone), {})

        for user in self.users:
            row = [self.get_user_link(user)]
            total_active = active_data.get(user.user_id, 0)
            total_closed = closed_data.get(user.user_id, 0)
            total_inactive = inactive_data.get(user.user_id, 0)
            total = total_active + total_closed
            for ld in landmark_data:
                value = ld.get(user.user_id, 0)
                row.append(_numeric_val(_format_val(value, total), value))
            row.append(_numeric_val(total_active))
            row.append(_numeric_val(total_closed))
            row.append(_numeric_val(total_inactive))
            rows.append(row)

        total_row = ["All Users"]
        for i in range(1, len(self.landmarks)+4):
            total_row.append(sum([row[i].get('sort_key', 0) for row in rows]))
        grand_total = sum(total_row[-3:-1])
        for i, val in enumerate(total_row[1:-3]):
            total_row[1+i] = _numeric_val(_format_val(val, grand_total), val)
        self.total_row = total_row

        return rows

    def fetch_cached_report(self):
        report = CaseActivityReportCache.get_by_domain(self.domain).first()
        if not report:
            logging.info("Building new Case Activity report for project %s" % self.domain)
            report = CaseActivityReportCache.build_report(self.domain_object)
        if not hasattr(report, 'closed_cases') or '__DEFAULT__' not in report.closed_cases:
            # temporary measure
            logging.info("Rebuilding Case Activity Report for project %s, missing Closed Cases." % self.domain)
            report = report.build_report(self.domain_object)
        return report


class SubmissionsByFormReport(WorkerMonitoringReportTable, DatespanMixin):
    name = "Submissions By Form"
    slug = "submissions_by_form"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
                'corehq.apps.reports.fields.GroupField',
                'corehq.apps.reports.fields.DatespanField']
    fix_left_col = True

    _form_types = None
    @property
    def form_types(self):
        if self._form_types is None:
            form_types = self._get_form_types()
            self._form_types = form_types if form_types else set()
        return self._form_types

    _all_submissions = None
    @property
    def all_submissions(self):
        if self._all_submissions is None:
            self._all_submissions = XFormInstance.view('reports/all_submissions',
                startkey=[self.domain, self.datespan.startdate_param_utc],
                endkey=[self.domain, self.datespan.enddate_param_utc],
                include_docs=True,
                reduce=False
            )
        return self._all_submissions

    @property
    def headers(self):
        form_names = [xmlns_to_name(*id_tuple) for id_tuple in self.form_types]
        form_names = [name.replace("/", " / ") if name is not None else '(No name)' for name in form_names]
        if self.form_types:
            # this fails if form_names, form_types is [], []
            form_names, self._form_types = zip(*sorted(zip(form_names, self.form_types)))

        headers = DataTablesHeader(DataTablesColumn("User", span=3))
        for name in list(form_names):
            headers.add_column(DataTablesColumn(name, sort_type=DTSortType.NUMERIC))
        headers.add_column(DataTablesColumn("All Forms", sort_type=DTSortType.NUMERIC))
        return headers

    @property
    def rows(self):
        counts = self._get_form_counts()
        rows = []
        totals_by_form = defaultdict(int)
        for user in self.users:
            row = []
            for form_type in self.form_types:
                try:
                    count = counts[user.user_id][form_type]
                    row.append(count)
                    totals_by_form[form_type] += count
                except Exception:
                    row.append(0)
            row_sum = sum(row)
            rows.append([self.get_user_link(user)] + \
                        [util.format_datatables_data(row_data, row_data) for row_data in row] + \
                        [util.format_datatables_data("<strong>%s</strong>" % row_sum, row_sum)])

        totals_by_form = [totals_by_form[form_type] for form_type in self.form_types]
        self.total_row = ["All Users"] + \
                         ["%s" % t for t in totals_by_form] + \
                         ["<strong>%s</strong>" % sum(totals_by_form)]
        return rows

    def _get_form_types(self):
        form_types = set()
        for submission in self.all_submissions:
            try:
                xmlns = submission['xmlns']
            except KeyError:
                xmlns = None

            try:
                app_id = submission['app_id']
            except Exception:
                app_id = None

            if self.user_ids:
                try:
                    userID = submission['form']['meta']['userID']
                except Exception:
                    pass
                else:
                    if userID in self.user_ids:
                        form_types.add(FormType(self.domain, xmlns, app_id).get_id_tuple())
            else:
                form_types.add(FormType(self.domain, xmlns, app_id).get_id_tuple())

        return sorted(form_types)

    def _get_form_counts(self):
        counts = defaultdict(lambda: defaultdict(int))
        for sub in self.all_submissions:
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
                if userID in self.user_ids:
                    counts[userID][FormType(self.domain, sub['xmlns'], app_id).get_id_tuple()] += 1
        return counts


class DailyReport(WorkerMonitoringReportTable, DatespanMixin):
    # overrides
    fix_left_col = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    # new class properties
    dates_in_utc = True
    couch_view = None

    _dates = None
    @property
    def dates(self):
        if self._dates is None:
            date_list = [self.datespan.startdate]
            while date_list[-1] < self.datespan.enddate:
                date_list.append(date_list[-1] + datetime.timedelta(days=1))
            self._dates = date_list
        return self._dates

    @property
    def headers(self):
        headers = DataTablesHeader(DataTablesColumn("Username", span=3))
        for d in self.dates:
            headers.add_column(DataTablesColumn(d.strftime(DATE_FORMAT), sort_type=DTSortType.NUMERIC))
        headers.add_column(DataTablesColumn("Total", sort_type=DTSortType.NUMERIC))
        return headers

    @property
    def rows(self):
        if self.dates_in_utc:
            _dates = [tz_utils.adjust_datetime_to_timezone(date, self.timezone.zone, pytz.utc.zone) for date in self.dates]
        else:
            _dates = self.dates
        date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(_dates)])

        key = [self.domain]
        results = get_db().view(
            self.couch_view,
            reduce=False,
            startkey=key+[self.datespan.startdate_param_utc if self.dates_in_utc else self.datespan.startdate_param],
            endkey=key+[self.datespan.enddate_param_utc if self.dates_in_utc else self.datespan.enddate_param]
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
            rows[i][0] = self.get_user_link(user)
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
    dates_in_utc = False


class FormCompletionTrendsReport(WorkerMonitoringReportTable, DatespanMixin):
    name = "Form Completion Trends"
    slug = "completion_times"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectFormField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("User"),
            DataTablesColumn("Average duration"),
            DataTablesColumn("Shortest"),
            DataTablesColumn("Longest"),
            DataTablesColumn("No. of Forms"))

    @property
    def rows(self):
        form = self.request_params.get('form', '')
        rows = []
        if not form:
            return rows

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
            rows.append([self.get_user_link(user),
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


class FormCompletionVsSubmissionTrendsReport(WorkerMonitoringReportTable, DatespanMixin):
    name = "Form Completion vs. Submission Trends"
    slug = "completion_vs_submission"
    
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectAllFormField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.SelectMobileWorkerField',
              'corehq.apps.reports.fields.DatespanField']

    @property
    def headers(self):
        return DataTablesHeader(DataTablesColumn("User", span=3),
            DataTablesColumn("Completion Time", span=2),
            DataTablesColumn("Submission Time", span=2),
            DataTablesColumn("View", sortable=False, span=2),
            DataTablesColumn("Difference", sort_type=DTSortType.NUMERIC, span=3)
        )

    @property
    def rows(self):
        rows = list()
        prefix = ["user"]
        selected_form = self.request_params.get('form')
        if selected_form:
            prefix.append("form_type")
        total = 0
        total_seconds = 0
        for user in self.users:
            key = [" ".join(prefix), self.domain, user.userID]
            if selected_form:
                key.append(selected_form)
            data = get_db().view("reports/completion_vs_submission",
                startkey=key+[self.datespan.startdate_param_utc],
                endkey=key+[self.datespan.enddate_param_utc],
                reduce=False
            ).all()
            for item in data:
                vals = item.get('value')
                completion_time = dateutil.parser.parse(vals.get('completion_time')).replace(tzinfo=None)
                completion_dst = False if self.timezone == pytz.utc else\
                tz_utils.is_timezone_in_dst(self.timezone, completion_time)
                completion_time = self.timezone.localize(completion_time, is_dst=completion_dst)
                submission_time = dateutil.parser.parse(vals.get('submission_time'))
                submission_time = submission_time.replace(tzinfo=pytz.utc)
                td = submission_time-completion_time

                td_total = (td.seconds + td.days * 24 * 3600)
                rows.append([
                    self.get_user_link(user),
                    self._format_date(completion_time),
                    self._format_date(submission_time),
                    self._view_form_link(item.get('id', '')),
                    util.format_datatables_data(text=self._format_td_status(td), sort_key=td_total)
                ])

                if td_total >= 0:
                    total_seconds += td_total
                    total += 1

        self.total_row = ["Average", "-", "-", "-", self._format_td_status(int(total_seconds/total), False) if total > 0 else "--"]
        return rows

    def _format_date(self, date, d_format="%d %b %Y, %H:%M"):
        return util.format_datatables_data(
            "%s (%s)" % (date.strftime(d_format), date.tzinfo._tzname),
            date
        )

    def _format_td_status(self, td, use_label=True):
        status = list()
        template = '<span class="label %(klass)s">%(status)s</span>'
        klass = ""
        if isinstance(td, int):
            td = datetime.timedelta(seconds=td)
        if isinstance(td, datetime.timedelta):
            hours = td.seconds//3600
            minutes = (td.seconds//60)%60
            vals = [td.days, hours, minutes, (td.seconds - hours*3600 - minutes*60)]
            names = ["day", "hour", "minute", "second"]
            status = ["%s %s%s" % (val, names[i], "s" if val != 1 else "") for (i, val) in enumerate(vals) if val > 0]

            if td.days > 1:
                klass = "label-important"
            elif td.days == 1:
                klass = "label-warning"
            elif hours > 5:
                klass = "label-info"
            if not status:
                status.append("same")
            elif td.days < 0:
                status = ["submitted before completed [strange]"]
                klass = "label-inverse"

        if use_label:
            return template % dict(status=", ".join(status), klass=klass)
        else:
            return ", ".join(status)

    def _view_form_link(self, instance_id):
        return '#'
        #todo fix
#        return '<a class="btn" href="%s">View Form</a>' % reverse('render_form_data', args=[self.domain, instance_id])



class SubmissionTimesReport(WorkerMonitoringChart):
    name = "Submission Times"
    slug = "submit_time_punchcard"

    report_partial_path = "reports/partials/punchcard.html"
    show_time_notice = True

    @property
    def report_context(self):
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
        return dict(
            chart_url=self.generate_chart(data)
        )

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


class SubmitDistributionReport(WorkerMonitoringChart):
    name = "Submit Distribution"
    slug = "submit_distribution"

    report_partial_path = "reports/partials/generic_piechart.html"

    @property
    def report_context(self):
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
                    predata[form_name]["description"] = "(%s) submissions of %s" %\
                                                        (predata[form_name]["value"], form_name)
                else:
                    predata[form_name] = {"display": form_name,
                                          "value": row["value"],
                                          "description": "(%s) submissions of %s" %\
                                                         (row["value"], form_name)}
        for value in predata.values():
            data.append(value)
        return dict(
            chart_data=data,
            user_id=self.individual,
            graph_width=900,
            graph_height=500
        )
