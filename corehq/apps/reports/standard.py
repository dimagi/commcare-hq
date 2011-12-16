from datetime import timedelta
from corehq.apps.groups.models import Group
from corehq.apps.reports.custom import TabularHQReport, ReportField
from corehq.apps.reports.models import HQUserType, HQUserToggle
from dimagi.utils.couch.database import get_db
from dimagi.utils.dates import DateSpan
from corehq.apps.reports import util
from dimagi.utils.web import json_request

DATE_FORMAT = "%Y-%m-%d"

class StandardHQReport(TabularHQReport):
    user_filter = HQUserType.use_defaults()

    def update_datespan(self):
        if self.request.datespan.is_valid():
            self.datespan = self.request.datespan

    def get_report_context(self):
        self.user_filter, _ = util.get_user_filter(self.request)
        self.update_datespan()
        super(StandardHQReport, self).get_report_context()

class DailySubmissionsReport(StandardHQReport):
    datespan = DateSpan.since(7, format="%Y-%m-%d")
    name = "Daily Form Submissions"
    slug = "daily_submissions"
    fields = ['corehq.apps.reports.standard.FilterUsersField',
              'corehq.apps.reports.standard.GroupField']

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

        group, registered_users = util.get_group_params(self.domain, **json_request(self.request.GET))
        registered_user_map = dict([(user.user_id, i) for (i, user) in enumerate(registered_users)])

        blank_row = [0]*(1+len(date_map))

        rows = dict()
        for index, utype in enumerate(HQUserType.human_readable):
            if index == HQUserType.REGISTERED:
                rows[utype] = [list(blank_row) for _ in range(len(registered_users))]
            elif index == HQUserType.UNKNOWN:
                rows[utype] = dict()
            else:
                rows[utype] = list(blank_row)
                rows[utype][0] = utype

        for result in results:
            _, date, user_id = result['key']
            val = result['value']
            if user_id in registered_user_map:
                rows[HQUserType.human_readable[HQUserType.REGISTERED]][registered_user_map[user_id]][date_map[date]] = val
            else:
                user_info = get_db().view(
                    'reports/submit_history',
                    startkey=[self.domain, user_id],
                    limit=1,
                    reduce=False
                ).one()
                username = user_info['value']['username']

                if username in HQUserType.human_readable:
                    rows[username][date_map[date]] = val
                else:
                    unregistered = HQUserType.human_readable[HQUserType.REGISTERED]
                    if not username in unregistered_rows:
                        rows[unregistered][username] = list(blank_row)
                        rows[unregistered][username][0] = username
                    rows[unregistered][username][date_map[date]] = val

        for i, user in enumerate(registered_users):
            rows[HQUserType.human_readable[HQUserType.REGISTERED]][i][0] = user.raw_username

        final_rows = []
        for user_type in self.user_filter:
            if user_type.show:
                if user_type.type == HQUserType.UNKNOWN:
                    for key, value in rows[user_type.name]:
                        final_rows.append(value)
                elif user_type.type == HQUserType.REGISTERED:
                    final_rows.extend(rows[user_type.name])
                else:
                    final_rows.append(rows[user_type.name])

        print "\n\nrows ", rows
        
        return final_rows


class GroupField(ReportField):
    slug = "group"
    template = "reports/partials/fields/select_group.html"

    def update_context(self):
        group = self.request.GET.get('group', '')
        groups = Group.by_domain(self.domain)
        if group:
            group = Group.get(group)
        self.context['group'] = group
        self.context['groups'] = groups

class FilterUsersField(ReportField):
    slug = "ufilter"
    template = "reports/partials/fields/filter_users.html"

    def update_context(self):
        toggle, show_filter = util.get_user_filter(self.request)
        self.context['show_user_filter'] = show_filter
        self.context['toggle_users'] = toggle