import datetime

from django.views.generic import TemplateView
from django.http import HttpResponse, Http404

from couchdbkit.exceptions import ResourceNotFound

from corehq.apps.reports.standard import CustomProjectReport
from dimagi.utils.couch.database import get_db

from .models import LegacyWeeklyReport
from .constants import *

class LegacyMixin(object):
    """
    Contains logic specific to this report.
    """
    user = None
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
        if not self.user in self._report.individual:
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
            'icon': icon,
        }


class LegacyReportView(LegacyMixin, CustomProjectReport):
    name = "Legacy Report"
    slug = "legacy"
    description = "Legacy Report for Pennsylvania State University"
    base_template = "penn_state/smiley_report.html"
    asynchronous = False

    @property
    def report_context(self):
        # import bpdb; bpdb.set_trace()
        self.user = self.request.GET.get('user') or \
            self.request.user.username.split("@")[0]
        self.report_id = self.request.GET.get('r_id', None)

        def get_individual(field):
            return self.report.individual.get(self.user).get(field)
        return {
            'site_strategy': self.context_for(
                self.report.site_strategy, 'peace'),
            'site_game': self.context_for(
                self.report.site_game, 'smiley'),
            'individual_strategy': self.context_for(
                get_individual('strategy'), 'peace'),
            'individual_game': self.context_for(
                get_individual('game'), 'smiley'),
        }
