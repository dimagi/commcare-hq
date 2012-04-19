from _collections import defaultdict
import datetime
import json
import logging
import sys
import dateutil
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.defaultfilters import yesno
from django.utils import html
import pytz
from restkit.errors import RequestFailed
from casexml.apps.case.models import CommCareCase
from corehq.apps.app_manager.models import Application
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports import util
from corehq.apps.reports.calc import entrytimes
from corehq.apps.reports.custom import HQReport
from corehq.apps.reports.display import xmlns_to_name, FormType
from corehq.apps.reports.fields import FilterUsersField, CaseTypeField, SelectCHWField
from corehq.apps.reports.models import HQUserType, FormExportSchema
from couchexport.models import SavedExportSchema
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import DatatablesParams
from dimagi.utils.dates import DateSpan, force_to_datetime
from dimagi.utils.parsing import json_format_datetime, string_to_datetime
from dimagi.utils.timezones import utils as tz_utils
from dimagi.utils.web import json_request, get_url_base

DATE_FORMAT = "%Y-%m-%d"

class StandardHQReport(HQReport):
    user_filter = HQUserType.use_defaults()
    fields = ['corehq.apps.reports.fields.FilterUsersField']
    history = None
    use_json = False
    hide_filters = False
    custom_breadcrumbs = None

    def get_global_params(self):
        self.request_params = json_request(self.request.GET)
        hist_param = self.request_params.get('history', None)
        if hist_param:
            self.history = datetime.datetime.strptime(hist_param, DATE_FORMAT)
        self.user_filter, _ = FilterUsersField.get_user_filter(self.request)

        self.group = self.request_params.get('group','')
        self.individual = self.request_params.get('individual', '')
        self.case_type = self.request_params.get('case_type', '')

        self.users = util.get_all_users_by_domain(self.domain, self.group, self.individual, self.user_filter)

        if self.individual:
            self.name = "%s for %s" % (self.name, self.users[0].raw_username)
        self.get_parameters()
        self.context['report_hide_filters'] = self.hide_filters
        self.context['report_breadcrumbs'] = self.custom_breadcrumbs

    def get_parameters(self):
        # here's where you can define any extra parameters you want to process before
        # proceeding with the rest of get_report_context
        pass

    def get_report_context(self):
        self.context['standard_report'] = True
        self.context['layout_flush_content'] = True
        self.build_selector_form()
        self.context.update(util.report_context(self.domain,
                                        report_partial = self.report_partial,
                                        title = self.name,
                                        headers = self.headers,
                                        rows = self.rows,
                                        show_time_notice = self.show_time_notice
                                      ))
    
    def as_view(self):
        self.get_global_params()
        return super(StandardHQReport, self).as_view()

    def as_json(self):
        self.get_global_params()
        return super(StandardHQReport, self).as_json()


class StandardTabularHQReport(StandardHQReport):
    total_row = None
    default_rows = 10
    start_at_row = 0

#    exportable = True
    def get_headers(self):
        return self.headers

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
            self.context['ajax_params'] = [{'name': 'individual', 'value': self.individual},
                                            {'name': 'group', 'value': self.group},
                                            {'name': 'casetype', 'value': self.case_type},
                                            {'name': 'ufilter', 'value': [f.type for f in self.user_filter if f.show]}]
        else:
            self.context['ajax_source'] = False
            self.context['ajax_params'] = False

        self.headers = self.get_headers()
        self.rows = self.get_rows()

        self.context['header'] = self.headers
        self.context['rows'] = self.rows
        if self.total_row:
            self.context['total_row'] = self.total_row

        super(StandardTabularHQReport, self).get_report_context()


class PaginatedHistoryHQReport(StandardTabularHQReport):
    use_json = True
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectCHWField']

    def get_parameters(self):
        self.userIDs = [user.user_id for user in self.users]
        self.usernames = dict([(user.user_id, user.username_in_report) for user in self.users])

    def json_data(self):
        params = DatatablesParams.from_request_dict(self.request.REQUEST)
        rows = self.paginate_rows(params.start, params.count)
        return {
            "sEcho": params.echo,
            "iTotalDisplayRecords": self.count,
            "iTotalRecords": self.count,
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

    def get_global_params(self):
        if self.request.datespan.is_valid() and not self.request.datespan.is_default:
            self.datespan.enddate = self.request.datespan.enddate
            self.datespan.startdate = self.request.datespan.startdate
            self.datespan.is_default = False
        self.request.datespan = self.datespan
        super(StandardDateHQReport, self).get_global_params()

    def get_report_context(self):
        self.context['datespan'] = self.datespan
        super(StandardDateHQReport, self).get_report_context()

class CaseActivityReport(StandardTabularHQReport):
    name = 'Case Activity'
    slug = 'case_activity'
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.CaseTypeField',
              'corehq.apps.reports.fields.GroupField']
    all_users = None
    display_data = ['percent']

    def get_parameters(self):
        landmarks_param = self.request_params.get('landmarks', [30,60,120])
        self.landmarks = [datetime.timedelta(days=l) for l in landmarks_param]+[None]
        self.now = datetime.datetime.now(tz=self.timezone)
        if self.history:
            self.now = self.history

    def get_headers(self):
        return ["User"] + \
               [util.format_datatables_header("Last %s Days" % l.days if l
                            else "Ever", sort_type=util.SORT_TYPE_NUMERIC) for l in self.landmarks]

    def get_rows(self):
        self.display_data = self.request_params.get('display', ['percent'])

        data = defaultdict(list)
        for user in self.users:
            for landmark in self.landmarks:
                data[user].append(self.get_number_cases_updated(user.user_id, landmark))

        extra = {}
        num_landmarks = len(self.landmarks)
        all_users = [dict(total=0, diff=0, next=None, last=0, percent=None) for _ in range(num_landmarks)]
        
        for user in data:
            extra[user] = []
            for i in range(num_landmarks):
                next = data[user][i+1] if i+1 < num_landmarks else None
                last = data[user][i-1] if i else 0
                current = data[user][i]
                all_users[i]["total"] += current
                extra[user].append({
                    "total": current,
                    "diff": current - last,
                    "next": next,
                    "last": last,
                    "percent": 1.0*current/next if next else None
                })

        for i in range(num_landmarks):
            if i > 0:
                all_users[i]["last"] = all_users[i-1]["total"]
            if i+1 < num_landmarks:
                all_users[i]["next"] = all_users[i+1]["total"]
            all_users[i]["diff"] = all_users[i]["total"] - all_users[i]["last"]
            all_users[i]["percent"] = 1.0*all_users[i]["total"]/all_users[i]["next"] if all_users[i]["next"] else None

        self.all_users = all_users

        rows = []
        for user in extra:
            row = [self.user_cases_link(user)]
            for entry in extra[user]:
                row = self.format_row(row, entry)
            rows.append(row)

        total_row = ["All Users"]
        for cumulative in self.all_users:
            total_row = self.format_row(total_row, cumulative)
        self.total_row = total_row

        return rows

    def format_row(self, row, entry):
        unformatted = entry['total']
        if entry['total'] == entry['diff'] or 'diff' not in self.display_data:
            fmt = "{total}"
        else:
            fmt = "+ {diff} = {total}"

        if entry['percent'] and 'percent' in self.display_data:
            fmt += " ({percent:.0%} of {next})"
        formatted = fmt.format(**entry)
        try:
            formatted = int(formatted)
        except ValueError:
            pass
        row.append(util.format_datatables_data(formatted, unformatted))
        return row


    def get_number_cases_updated(self, user_id, landmark=None):
        utc_now = tz_utils.adjust_datetime_to_timezone(self.now, self.timezone.zone, pytz.utc.zone)
        start_time_json = json_format_datetime(utc_now - landmark) if landmark else ""
        key = [self.domain, self.case_type or {}, user_id]
        r = get_db().view('case/by_last_date',
            startkey=key + [start_time_json],
            endkey=key + [json_format_datetime(utc_now)],
            group=True,
            group_level=0
        ).one()
        return r['value']['count'] if r else 0

    def user_cases_link(self, user):
        template = '<a href="%(link)s?individual=%(user_id)s">%(username)s</a>'
        return template % {"link": "%s%s" % (get_url_base(), reverse("report_dispatcher", args=[self.domain, CaseListReport.slug])),
                           "user_id": user.user_id,
                           "username": user.username_in_report}

class DailyReport(StandardDateHQReport, StandardTabularHQReport):
    couch_view = ''
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']

    def get_headers(self):
        self.dates = [self.datespan.startdate]
        while self.dates[-1] < self.datespan.enddate:
            self.dates.append(self.dates[-1] + datetime.timedelta(days=1))
        return ["Username"] + \
               [util.format_datatables_header(d.strftime(DATE_FORMAT), sort_type=util.SORT_TYPE_NUMERIC) for d in self.dates] + \
               [util.format_datatables_header("Total", sort_type=util.SORT_TYPE_NUMERIC)]

    def get_rows(self):
        utc_dates = [tz_utils.adjust_datetime_to_timezone(date, self.timezone.zone, pytz.utc.zone) for date in self.dates]
        date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(utc_dates)])

        results = get_db().view(
            self.couch_view,
            group=True,
            startkey=[self.domain,
                      tz_utils.adjust_datetime_to_timezone(self.datespan.startdate, self.timezone.zone, pytz.utc.zone).isoformat()],
            endkey=[self.domain,
                    tz_utils.adjust_datetime_to_timezone(self.datespan.enddate, self.timezone.zone, pytz.utc.zone).isoformat(), {}]
        ).all()
        user_map = dict([(user.user_id, i) for (i, user) in enumerate(self.users)])
        userIDs = [user.user_id for user in self.users]
        rows = [[0]*(2+len(date_map)) for _ in range(len(self.users))]
        total_row = [0]*(2+len(date_map))

        for result in results:
            _, date, user_id = result['key']
            val = result['value']
            if user_id in userIDs:
                rows[user_map[user_id]][date_map[date]] = val

        for i, user in enumerate(self.users):
            rows[i][0] = user.username_in_report
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

    def get_parameters(self):
        self.form_types = self.get_relevant_form_types()

    def get_headers(self):
        form_names = [xmlns_to_name(*id_tuple) for id_tuple in self.form_types]
        form_names = [name.replace("/", " / ") for name in form_names]

        if self.form_types:
            # this fails if form_names, form_types is [], []
            form_names, self.form_types = zip(*sorted(zip(form_names, self.form_types)))

        return ['User'] + [util.format_datatables_header(name, sort_type=util.SORT_TYPE_NUMERIC) for name in list(form_names)] + \
               [util.format_datatables_header("All Forms", sort_type=util.SORT_TYPE_NUMERIC)]

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
            rows.append([user.username_in_report] + [util.format_datatables_data(row_data, row_data) for row_data in row] + [util.format_datatables_data("* %s" % row_sum, row_sum)])

        totals_by_form = [totals_by_form[form_type] for form_type in self.form_types]
        self.total_row = ["All Users"] + ["%s" % t for t in totals_by_form] + ["* %s" % sum(totals_by_form)]

        return rows

    def get_submissions_by_form_json(self):
        userIDs = [user.user_id for user in self.users]
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
        return ["User", "Average duration", "Shortest", "Longest", "# Forms"]

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
                rows.append([user.username_in_report,
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
                rows.insert(0, ["-- Total --",
                                to_minutes(float(totalsum), float(totalcount)),
                                to_minutes(globalmin),
                                to_minutes(globalmax),
                                totalcount])
        return rows


class SubmitHistory(PaginatedHistoryHQReport):
    name = 'Submit History'
    slug = 'submit_history'

    def get_headers(self):
        return ["View Form", "Username", "Submit Time", "Form"]

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
                xmlns = xmlns_to_name(self.domain, xmlns)
                rows.append([self.form_data_link(data.instanceID), self.usernames[data.userID], time, xmlns])
        return rows

    def form_data_link(self, instance_id):
        return "<a class='ajax_dialog' href='%s'>View Form</a>" % reverse('render_form_data', args=[self.domain, instance_id])


class CaseListReport(PaginatedHistoryHQReport):
    name = 'Case List'
    slug = 'case_list'
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectCHWField',
              'corehq.apps.reports.fields.CaseTypeField']

    def get_report_context(self):
        self.context.update({"filter": settings.LUCENE_ENABLED })
        super(PaginatedHistoryHQReport, self).get_report_context()

    def get_headers(self):
        final_headers = ["Name", "User", "Created Date", "Modified Date", "Status"]
        if not self.individual:
            self.name = "%s for %s" % (self.name, SelectCHWField.get_default_text(self.user_filter))
        if not self.case_type:
            final_headers = ["Case Type"] + final_headers
        open, all = CaseTypeField.get_case_counts(self.domain, self.case_type, self.userIDs)
        if all > 0:
            self.name = "%s (%s/%s open)" % (self.name, open, all)
        else:
            self.name = "%s (empty)" % self.name
        return final_headers

    def paginate_rows(self, skip, limit):
        rows = []
        self.count = 0

        if settings.LUCENE_ENABLED:
            search_key = self.request_params.get("sSearch", "")
            query = "domain:(%s)" % self.domain
            query = "%s AND user_id:(%s)" % (query, " OR ".join(self.userIDs))
            if self.case_type:
                query = "%s AND type:%s" % (query, self.case_type)
            if search_key:
                query = "(%s) AND %s" % (search_key, query)

            results = get_db().search("case/search", q=query,
                                      handler="_fti/_design",
                                      limit=limit, skip=skip, sort="\sort_modified")
            try:
                for row in results:
                    row = self.format_row(row)
                    if row is not None:
                        rows.append(row)
                self.count = results.total_rows
            except RequestFailed:
                pass
                # just ignore poorly formatted search terms for now

        return rows

    def format_row(self, row):
        if "doc" in row:
            case = CommCareCase.wrap(row["doc"])
        elif "id" in row:
            case = CommCareCase.get(row["id"])
        else:
            raise ValueError("Can't construct case object from row result %s" % row)

        if case.domain != self.domain:
            logging.error("case.domain != self.domain; %r and %r, respectively" % (case.domain, self.domain))

        assert(case.domain == self.domain)

        return ([] if self.case_type else [case.type]) + [
            self.case_data_link(row['id'], case.name),
            self.usernames[case.user_id],
            self.date_to_json(case.opened_on),
            self.date_to_json(case.modified_on),
            yesno(case.closed, "closed,open")
        ]

    def date_to_json(self, date):
        return tz_utils.adjust_datetime_to_timezone\
            (date, pytz.utc.zone, self.timezone.zone).strftime\
            ('%Y-%m-%d %H:%M:%S') if date else ""

    def case_data_link(self, case_id, case_name):
        return "<a class='ajax_dialog' href='%s'>%s</a>" % \
                    (reverse('case_details', args=[self.domain, case_id]),
                     case_name)


class SubmissionTimesReport(StandardHQReport):
    name = "Submission Times"
    slug = "submit_time_punchcard"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.SelectCHWField']
    template_name = "reports/basic_report.html"
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

                #adjust to timezone
                now = datetime.datetime.utcnow()
                report_time = datetime.datetime(now.year, now.month, now.day, hour, tzinfo=pytz.utc)
                report_time = tz_utils.adjust_datetime_to_timezone(report_time, pytz.utc.zone, self.timezone.zone)
                hour = report_time.hour

                data["%d %02d" % (day, hour)] = data["%d %02d" % (day, hour)] + row["value"]
        self.context["chart_url"] = self.generate_chart(data)
        self.context["timezone_now"] = datetime.datetime.now(tz=self.timezone)
        self.context["timezone"] = self.timezone.zone

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
              'corehq.apps.reports.fields.SelectCHWField']
    template_name = "reports/basic_report.html"
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
                form_name = xmlns_to_name(self.domain, xmlns)
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

class SubmitTrendsReport(StandardDateHQReport):
    #nuked until further notice
    name = "Submit Trends"
    slug = "submit_trends"
    fields = ['corehq.apps.reports.fields.SelectCHWField',
              'corehq.apps.reports.fields.DatespanField']
    template_name = "reports/basic_report.html"
    report_partial = "reports/partials/formtrends.html"

    def calc(self):
        self.context.update({
            "user_id": self.individual,
        })

class ExcelExportReport(StandardDateHQReport):
    """
    Note: .deid.FormDeidExport subclasses me, so be mindful if you want to change me
    """
    name = "Export Submissions to Excel"
    slug = "excel_export_data"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField',
              'corehq.apps.reports.fields.DatespanField']
    template_name = "reports/reportdata/excel_export_data.html"

    def get_default_datespan(self):
        datespan = super(ExcelExportReport, self).get_default_datespan()
        datespan.startdate = get_db().view('reports/all_submissions',
            startkey=[self.domain],
            limit=1,
            descending=False,
            reduce=False,
            # The final 'Z' makes the datetime parse with tzinfo=tzlocal()
            wrapper=lambda x: string_to_datetime(x['key'][1]).replace(tzinfo=None)
        ).one()
        return datespan

    def get_saved_exports(self):
        """
        add saved exports. because of the way in which the key is stored
        (serialized json) this is a little bit hacky, but works.

        """
        startkey = json.dumps([self.domain, ""])[:-3]
        endkey = "%s{" % startkey
        exports = FormExportSchema.view("couchexport/saved_export_schemas",
            startkey=startkey, endkey=endkey,
            include_docs=True)

        exports = filter(lambda x: x.type == "form", exports)
        return exports


    def calc(self):
        # This map for this view emits twice, once with app_id and once with {}, letting you join across all app_ids.
        # However, we want to separate out by (app_id, xmlns) pair not just xmlns so we use [domain] to [domain, {}]
        forms = []
        unknown_forms = []
        for f in get_db().view('reports/forms_by_xmlns', startkey=[self.domain], endkey=[self.domain, {}], group=True):
            form = f['value']
            if 'app' in form:
                form['has_app'] = True
            else:
                app_id = f['key'][1] or ''
                form['app'] = {
                    'id': app_id
                }
                form['has_app'] = False
                unknown_forms.append(form)
            forms.append(form)

        forms = sorted(forms, key=lambda form:\
            (0, form['app']['name'], form['app']['id'], form.get('module', {'id': -1})['id'], form.get('form', {'id': -1})['id'])\
            if form['has_app'] else\
            (1, form['xmlns'], form['app']['id'])
        )
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
                def __getitem__(self, item):
                    if not self.has_key(item):
                        self[app] = Application.get(item)
                    return super(AppCache, self).get(item)

            app_cache = AppCache()

            for form in unknown_forms:
                if form['app']['id']:
                    try:
                        app = app_cache[form['app']['id']]
                    except Exception:
                        form['app_does_not_exist'] = True
                        form['possibilities'] = possibilities[form['xmlns']]
                        if form['possibilities']:
                            form['duplicate'] = True
                    else:
                        if app.domain != self.domain:
                            logging.error("submission tagged with app from wrong domain: %s" % app.get_id)
                        else:
                            if app.copy_of:
                                app = app_cache[app.copy_of]
                                form['app_copy'] = {'id': app.get_id, 'name': app.name}
                            if app.is_deleted():
                                form['app_deleted'] = {'id': app.get_id}
                else:
                    form['possibilities'] = possibilities[form['xmlns']]
                    if form['possibilities']:
                        form['duplicate'] = True
                    else:
                        form['no_suggestions'] = True

        self.context.update({
            "forms": forms,
            "saved_exports": self.get_saved_exports(),
            "edit": self.request.GET.get('edit') == 'true',
            "get_filter_params": self.get_filter_params(),
        })

    def get_filter_params(self):
        params = self.request.GET.copy()
        params['startdate'] = self.datespan.startdate_display
        params['enddate'] = self.datespan.enddate_display
        return params


class CaseExportReport(StandardHQReport):
    name = "Export Cases, Referrals, and Users"
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
        return ["Username",
                util.format_datatables_header("Last Seen", sort_type=util.SORT_TYPE_NUMERIC),
                "CommCare Version", "Application [Deployed Build]"]

    def get_parameters(self):
        self.selected_app = self.request_params.get('app', '')

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
                now = datetime.datetime.now(tz=pytz.utc)
                time = datetime.datetime.replace(data.received_on, tzinfo=pytz.utc)
                dtime = now - time
                if dtime.days < 1:
                    dtext = "Today"
                elif dtime.days < 2:
                    dtext = "Yesterday"
                else:
                    dtext = "%s days ago" % dtime.days
                last_seen = util.format_datatables_data(dtext, dtime.days)

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
