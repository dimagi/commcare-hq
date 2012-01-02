from _collections import defaultdict
from datetime import timedelta, datetime
from corehq.apps.reports import util
from corehq.apps.reports.custom import TabularHQReport
from corehq.apps.reports.display import xmlns_to_name
from corehq.apps.reports.fields import FilterUsersField
from corehq.apps.reports.models import HQUserType
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.datespan import datespan_in_request
from dimagi.utils.parsing import json_format_datetime
from dimagi.utils.web import json_request

DATE_FORMAT = "%Y-%m-%d"

datespan_default = datespan_in_request(
    from_param="startdate",
    to_param="enddate",
    default_days=7,
)

class StandardTabularHQReport(TabularHQReport):
    user_filter = HQUserType.use_defaults()
    fields = ['corehq.apps.reports.fields.FilterUsersField']
    history = None

    def get_report_context(self):
        self.request_params = json_request(self.request.GET)
        hist_param = self.request_params.get('history', None)
        if hist_param:
            self.history = datetime.strptime(hist_param, DATE_FORMAT)
        self.user_filter, _ = FilterUsersField.get_user_filter(self.request)
        group = self.request_params.get('group','')
        self.users = util.get_users_by_type_and_group(self.domain, group, self.user_filter)
        super(StandardTabularHQReport, self).get_report_context()

    @classmethod
    def generate_row_map(cls, blank_row=[], registered_length=1):
        rows = dict()
        for index, utype in enumerate(HQUserType.human_readable):
            if index == HQUserType.REGISTERED:
                rows[utype] = [list(blank_row) for _ in range(registered_length)]
            elif index == HQUserType.UNKNOWN:
                rows[utype] = dict()
            else:
                rows[utype] = list(blank_row)
                rows[utype][0] = '<strong>%s</strong>' % utype
        return rows



class CaseActivityReport(StandardTabularHQReport):
    name = 'Case Activity'
    slug = 'case_activity'
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.CaseTypeField',
              'corehq.apps.reports.fields.GroupField']
    headers = ['yup']

    def get_headers(self):
        landmarks_param = self.request_params.get('landmarks', [30,60,120])
        self.landmarks = [timedelta(days=l) for l in landmarks_param]+[None]
        return ["User"] + [{"html": "Last %s Days" % l.days if l else "Ever", "sort_type": "title-numeric"} for l in self.landmarks]

    def get_rows(self):
        self.now = datetime.utcnow()
        if self.history:
            print "USING HISTORY"
            self.now = self.history
        display = self.request_params.get('display', ['percent'])

        data = defaultdict(list)
        for user in self.users:
            for landmark in self.landmarks:
                data[user].append(self.get_number_cases_updated(user.user_id, landmark))
        print data

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
            row = [user.username_in_report]
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








class StandardTabularHQReportWithDate(StandardTabularHQReport):
    datespan = DateSpan.since(7, format="%Y-%m-%d")

    def __init__(self, domain, request, base_context = {}):
        super(StandardTabularHQReportWithDate, self).__init__(domain, request, base_context)
        datespan_default(self.request)

    def update_datespan(self):
        if self.request.datespan.is_valid():
            self.datespan = self.request.datespan

    def get_report_context(self):
        self.update_datespan()
        super(StandardTabularHQReportWithDate, self).get_report_context()




class DailyReport(StandardTabularHQReportWithDate):
    couch_view = ''
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField']

    def get_headers(self):
        self.dates = [self.datespan.startdate]
        while self.dates[-1] < self.datespan.enddate:
            self.dates.append(self.dates[-1] + timedelta(days=1))
        return ["Username"] + [d.strftime(DATE_FORMAT) for d in self.dates]

    def get_rows(self):
        date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(self.dates)])

        results = get_db().view(
            self.couch_view,
            group=True,
            startkey=[self.domain, self.request.datespan.startdate.isoformat()],
            endkey=[self.domain, self.request.datespan.enddate.isoformat(), {}]
        ).all()
        print self.users
        user_map = dict([(user.user_id, i) for (i, user) in enumerate(self.users)])
        userIDs = [user.user_id for user in self.users]
        print user_map
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

class SubmissionsByFormReport(StandardTabularHQReportWithDate):
    name = "Submissions By Form"
    slug = "submissions_by_form"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField']

    def get_headers(self):
        self.form_types = self.get_relevant_form_types()
        form_names = [xmlns_to_name(xmlns, self.domain) for xmlns in self.form_types]
        form_names = [name.replace("/", " / ") for name in form_names]

        if self.form_types:
            # this fails if form_names, form_types is [], []
            form_names, self.form_types = zip(*sorted(zip(form_names, self.form_types)))

        return ['User'] + list(form_names) + ['All Forms']

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
                userID = sub['form']['meta']['userID']
                if (userIDs is None) or (userID in userIDs):
                    counts[userID][sub['xmlns']] += 1
            except Exception:
                # if a form don't even have a userID, don't even bother tryin'
                pass
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
            if userIDs is not None:
                try:
                    userID = submission['form']['meta']['userID']
                    if userID in userIDs:
                        form_types.add(xmlns)
                except Exception:
                    pass
            else:
                form_types.add(xmlns)

        return sorted(form_types)



    


    
