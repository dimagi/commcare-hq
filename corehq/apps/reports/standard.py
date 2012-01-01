from datetime import timedelta, datetime
from corehq.apps.reports import util
from corehq.apps.reports.custom import TabularHQReport
from corehq.apps.reports.fields import FilterUsersField
from corehq.apps.reports.models import HQUserType
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


class DailySubmissionsReport(StandardTabularHQReportWithDate):
    name = "Daily Form Submissions"
    slug = "daily_submissions"
    fields = ['corehq.apps.reports.fields.FilterUsersField',
              'corehq.apps.reports.fields.GroupField']

    def update_datespan(self):
        super(DailySubmissionsReport, self).update_datespan()
        self.dates = [self.datespan.startdate]
        while self.dates[-1] < self.datespan.enddate:
            self.dates.append(self.dates[-1] + timedelta(days=1))

    def get_headers(self):
        return ["Username"] + [d.strftime(DATE_FORMAT) for d in self.dates]

    def get_rows(self):
        date_map = dict([(date.strftime(DATE_FORMAT), i+1) for (i,date) in enumerate(self.dates)])

        results = get_db().view(
            'reports/daily_submissions',
            group=True,
            startkey=[self.domain, self.request.datespan.startdate.isoformat()],
            endkey=[self.domain, self.request.datespan.enddate.isoformat(), {}]
        ).all()

        group = self.request_params.get('group','')
        users = util.get_users_by_type_and_group(self.domain, group, self.user_filter)
        user_map = dict([(user.user_id, i) for (i, user) in enumerate(users)])
        rows = [[0]*(1+len(date_map)) for _ in range(len(users))]

        for result in results:
            _, date, user_id = result['key']
            val = result['value']
            
            if user_id in users:
               rows[user_map[user_id]][date_map[date]] = val

        for i, user in enumerate(users):
            rows[i][0] = user.username_in_report

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
        #print util.get_all_userids_submitted(self.domain)
        group = self.request_params.get('group','')
        util.get_users_by_type_and_group(self.domain, group, self.user_filter)
        return self.rows

    def get_number_cases_updated(self, chw, landmark=None):
        start_time_json = json_format_datetime(self.now - landmark) if landmark else ""
        key = [self.domain, self.case_type or {}, chw]
        r = get_db().view('case/by_last_date',
            startkey=key + [start_time_json],
            endkey=key + [json_format_datetime(self.now)],
            group=True,
            group_level=0
        ).one()
        return r['value']['count'] if r else 0
    


    
