from _collections import defaultdict
from datetime import timedelta, datetime
import sys
from django.conf import settings
from django.core.urlresolvers import reverse
from django.template.defaultfilters import yesno
from restkit.errors import RequestFailed
from casexml.apps.case.models import CommCareCase
from corehq.apps.hqsofabed.models import HQFormData
from corehq.apps.reports import util
from corehq.apps.reports.calc import entrytimes
from corehq.apps.reports.custom import HQReport
from corehq.apps.reports.display import xmlns_to_name, FormType
from corehq.apps.reports.fields import FilterUsersField, CaseTypeField, SelectCHWField, datespan_default
from corehq.apps.reports.models import HQUserType
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.couch.pagination import DatatablesParams
from dimagi.utils.dates import DateSpan
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.web import json_request, get_url_base

DATE_FORMAT = "%Y-%m-%d"

class StandardHQReport(HQReport):
    user_filter = HQUserType.use_defaults()
    fields = ['corehq.apps.reports.fields.FilterUsersField']
    history = None
    use_json = False

    def get_global_params(self):
        # call this in 
        self.request_params = json_request(self.request.GET)
        hist_param = self.request_params.get('history', None)
        if hist_param:
            self.history = datetime.strptime(hist_param, DATE_FORMAT)
        self.user_filter, _ = FilterUsersField.get_user_filter(self.request)

        self.group = self.request_params.get('group','')
        self.individual = self.request_params.get('individual', '')
        self.case_type = self.request_params.get('case_type', '')

        self.users = util.get_all_users_by_domain(self.domain, self.group, self.individual, self.user_filter)

        if self.individual:
            self.name = "%s for %s" % (self.name, self.users[0].raw_username)
        self.get_parameters()

    def get_parameters(self):
        # here's where you can define any extra parameters you want to process before
        # proceeding with the rest of get_report_context
        pass

    def get_report_context(self):
        self.context['standard_report'] = True
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

    def set_headers(self):
        return self.headers

    def set_rows(self):
        return self.rows

    def get_report_context(self):
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

        self.headers = self.set_headers()
        self.rows = self.set_rows()
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
    datespan = DateSpan.since(7, format="%Y-%m-%d")

    def __init__(self, domain, request, base_context = {}):
        super(StandardDateHQReport, self).__init__(domain, request, base_context)
        datespan_default(self.request)

    def get_global_params(self):
        if self.request.datespan.is_valid():
            self.datespan = self.request.datespan
        super(StandardDateHQReport, self).get_global_params()



class CaseActivityReport(StandardTabularHQReport):
    name = 'Case Activity'
    slug = 'case_activity'
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.CaseTypeField',
              'corehq.apps.reports.fields.GroupField']

    def get_parameters(self):
        landmarks_param = self.request_params.get('landmarks', [30,60,120])
        self.landmarks = [timedelta(days=l) for l in landmarks_param]+[None]
        self.now = datetime.utcnow()
        if self.history:
            self.now = self.history

    def set_headers(self):
        return ["User"] + [{"html": "Last %s Days" % l.days if l else "Ever",
                            "sort_type": "title-numeric"} for l in self.landmarks]

    def set_rows(self):
        display = self.request_params.get('display', ['percent'])

        data = defaultdict(list)
        for user in self.users:
            for landmark in self.landmarks:
                data[user].append(self.get_number_cases_updated(user.user_id, landmark))

        extra = {}

        for user in data:
            extra[user] = []
            for i in range(len(self.landmarks)):
                next = data[user][i+1] if i+1 < len(self.landmarks) else None
                last = data[user][i-1] if i else 0
                current = data[user][i]
                extra[user].append({
                    "total": current,
                    "diff": current - last,
                    "next": next,
                    "last": last,
                    "percent": 1.0*current/next if next else None
                })

        rows = []
        for user in extra:
            row = [self.user_cases_link(user)]
            for entry in extra[user]:
                unformatted = entry['total']
                if entry['total'] == entry['diff'] or 'diff' not in display:
                    fmt = "{total}"
                else:
                    fmt = "+ {diff} = {total}"

                if entry['percent'] and 'percent' in display:
                    fmt += " ({percent:.0%} of {next})"
                formatted = fmt.format(**entry)
                try:
                    formatted = int(formatted)
                except ValueError:
                    pass
                row.append({"html": formatted, "sort_key": unformatted})
            rows.append(row)

        return rows

    def get_number_cases_updated(self, user_id, landmark=None):
        start_time_json = json_format_datetime(self.now - landmark) if landmark else ""
        key = [self.domain, self.case_type or {}, user_id]
        r = get_db().view('case/by_last_date',
            startkey=key + [start_time_json],
            endkey=key + [json_format_datetime(self.now)],
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

    def set_headers(self):
        self.dates = [self.datespan.startdate]
        while self.dates[-1] < self.datespan.enddate:
            self.dates.append(self.dates[-1] + timedelta(days=1))
        return ["Username"] + [d.strftime(DATE_FORMAT) for d in self.dates]

    def set_rows(self):
        date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(self.dates)])

        results = get_db().view(
            self.couch_view,
            group=True,
            startkey=[self.domain, self.request.datespan.startdate.isoformat()],
            endkey=[self.domain, self.request.datespan.enddate.isoformat(), {}]
        ).all()
        user_map = dict([(user.user_id, i) for (i, user) in enumerate(self.users)])
        userIDs = [user.user_id for user in self.users]
        rows = [[0]*(1+len(date_map)) for _ in range(len(self.users))]

        for result in results:
            _, date, user_id = result['key']
            val = result['value']
            if user_id in userIDs:
                rows[user_map[user_id]][date_map[date]] = val

        for i, user in enumerate(self.users):
            rows[i][0] = user.username_in_report

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

    def set_headers(self):
        form_names = form_names = [xmlns_to_name(*id_tuple) for id_tuple in self.form_types]
        form_names = [name.replace("/", " / ") for name in form_names]

        if self.form_types:
            # this fails if form_names, form_types is [], []
            form_names, self.form_types = zip(*sorted(zip(form_names, self.form_types)))

        return ['User'] + list(form_names) + ['All Forms']

    def set_rows(self):
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
            rows.append([user.username_in_report] + row + ["* %s" % sum(row)])

        totals_by_form = [totals_by_form[form_type] for form_type in self.form_types]
        rows.append(["* All Users"] + ["* %s" % t for t in totals_by_form] + ["* %s" % sum(totals_by_form)])

        return rows

    def get_submissions_by_form_json(self):
        userIDs = [user.user_id for user in self.users]
        submissions = XFormInstance.view('reports/all_submissions',
            startkey=[self.domain, self.datespan.startdate_param],
            endkey=[self.domain, self.datespan.enddate_param],
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
            startkey=[self.domain, self.datespan.startdate_param],
            endkey=[self.domain, self.datespan.enddate_param],
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

    def set_headers(self):
        return ["User", "Average duration", "Shortest", "Longest", "# Forms"]

    def set_rows(self):
        form = self.request_params.get('form', '')
        rows = []

        if form:
            totalsum = totalcount = 0
            def to_minutes(val_in_ms, d=None):
                if val_in_ms is None or d == 0:
                    return None
                elif d:
                    val_in_ms /= d
                return timedelta(seconds=int((val_in_ms + 500)/1000))

            globalmin = sys.maxint
            globalmax = 0
            for user in self.users:
                datadict = entrytimes.get_user_data(self.domain, user.user_id, form, self.request.datespan)
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

    def set_headers(self):
        return ["View Form", "Username", "Submit Time", "Form"]

    def paginate_rows(self, skip, limit):
        rows = []
        all_hist = HQFormData.objects.filter(userID__in=self.userIDs, domain=self.domain)
        self.count = all_hist.count()
        history = all_hist.extra(order_by=['-received_on'])[skip:skip+limit]
        for data in history:
            if data.userID in self.userIDs:
                time = data.received_on
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

    def set_headers(self):
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

        assert(case.domain == self.domain)
        return ([] if self.case_type else [case.type]) + [
            self.case_data_link(row['id'], case.name),
            self.usernames[case.user_id],
            self.date_to_json(case.opened_on),
            self.date_to_json(case.modified_on),
            yesno(case.closed, "closed,open")
        ]

    @classmethod
    def date_to_json(cls, date):
        return date.strftime('%Y-%m-%d %H:%M:%S') if date else "",

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