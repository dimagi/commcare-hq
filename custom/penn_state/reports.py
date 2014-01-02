import datetime, copy

from django.views.generic import TemplateView
from django.http import HttpResponse

from couchdbkit.exceptions import ResourceNotFound
from no_exceptions.exceptions import Http403, Http404

from corehq.apps.users.models import CommCareUser
from corehq.apps.groups.models import Group
from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.couch.database import get_db

from .models import LegacyWeeklyReport
from .constants import *


class LegacyMixin(object):
    """
    Contains logic specific to this report.
    """
    report_id = None
    _report = None

    @property
    def report(self):
        if self._report is not None:
            return self._report
        if self.report_id is not None:
            try:
                self._report = LegacyWeeklyReport.get(self.report_id)
            except ResourceNotFound:
                raise Http404
        else:
            self._report = LegacyWeeklyReport.by_user(self.user)
            if self._report is None:
                raise Http404
        if not self.user.raw_username in self._report.individual:
            raise Http404
        return self._report

    def context_for(self, days, icon):
        """
        days should be a 5 element array, with each element representing
        the number done that day.  -1 means that day was off.
        icon should be either "smiley" or "peace"
        """
        days_on = [day for day in days if day >= 0]
        days_used = [day for day in days if day > 0]
        return {
            'days': zip(
                ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
                days,
            ),
            'total': sum(days_used),
            'days_used': len(days_used),
            'days_on': len(days_on),
            'days_missed': len(days_on) - len(days_used),
            'icon': icon,
        }


class LegacyAdminReport(object):
    @property
    def is_admin_report(self):
        return not self.request.GET.get('user') and \
            self.request.couch_user.is_domain_admin(DOMAIN)

    def aggregate_totals(self, weeks):
        sites = copy.deepcopy(weeks)
        week_sites = [site.pop() for site in sites if site]
        if not week_sites:
            return []
        return self.aggregate_totals(sites) + [[
            week_sites[0][0],
            sum([site[1] for site in week_sites])
        ]]

    @property
    def admin_report_context(self):
        reports = []
        for group in Group.by_domain(DOMAIN):
            if group._id in GROUPS:
                report = LegacyWeeklyReport.by_site(group)
                if report:
                    reports.append(report)
        def aggregate(attr):
            def _sum(ds):
                if not filter(lambda d: d>=0, ds):
                    return -1
                return sum(filter(lambda d: d>0, ds))
            return map(_sum, zip(
                *[getattr(r, attr) for r in reports]
            ))
        if reports:
            strategy = aggregate('site_strategy')
            game = aggregate('site_game')
            weekly = self.aggregate_totals([r.weekly_totals for r in reports])
        else:
            strategy = [-1]*5
            game = [-1]*5
            weekly = []
        return {
            'strategy': self.context_for(
                strategy, 'peace'),
            'game': self.context_for(
                game, 'smiley'),
            'weekly': weekly,
        }


class LegacyReportView(LegacyAdminReport, LegacyMixin, CustomProjectReport):
    name = "Legacy Report"
    slug = "legacy"
    description = "Legacy Report for Pennsylvania State University"
    asynchronous = False
    _user = None

    @property
    def base_template(self):
        if self.is_admin_report:
            return "penn_state/smiley_admin_report.html"
        else:
            return "penn_state/smiley_report.html"

    @property
    def user(self):
        if self._user is None:
            user_param = self.request.GET.get('user')
            if user_param:
                username = '%s@%s.commcarehq.org' % (user_param, DOMAIN)
                self._user = CommCareUser.get_by_username(username)
                # Check permissions
                if not self.request.couch_user.is_domain_admin(DOMAIN) and \
                        self.request.couch_user.raw_username != user_param:
                    raise Http403("You can only view your own report.")
            else:
                self._user = self.request.couch_user
            if self._user is None:
                raise Http404
        return self._user

    @property
    def report_context(self):
        if self.is_admin_report:
            return self.admin_report_context

        self.report_id = self.request.GET.get('r_id', None)

        def get_individual(field):
            return self.report.individual.get(self.user.raw_username).get(field)
        return {
            'site_strategy': self.context_for(
                self.report.site_strategy, 'peace'),
            'site_game': self.context_for(
                self.report.site_game, 'smiley'),
            'individual_strategy': self.context_for(
                get_individual('strategy'), 'peace'),
            'individual_game': self.context_for(
                get_individual('game'), 'smiley'),
            'site_weekly': self.report.weekly_totals,
            'individual_weekly': get_individual('weekly_totals'),
        }

