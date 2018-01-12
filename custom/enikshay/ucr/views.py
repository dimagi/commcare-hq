from __future__ import absolute_import
from __future__ import division

from datetime import datetime

from django.db.models import Min

from corehq.apps.userreports.models import AsyncIndicator
from corehq.apps.userreports.reports.view import CustomConfigurableReport


class MonitoredReport(CustomConfigurableReport):
    """For reports backed by an async datasource, shows an indication of how far
    behind the report might be, in increments of 12 hours.

    """

    template_name = 'enikshay/ucr/monitored_report.html'

    @property
    def page_context(self):
        context = super(MonitoredReport, self).page_context
        context['hours_behind'] = self.hours_behind()
        return context

    def hours_behind(self):
        """returns the number of hours behind this report is, to the nearest 12 hour bucket.
        """
        now = datetime.utcnow()

        try:
            oldest_indicator = (
                AsyncIndicator.objects
                .filter(indicator_config_ids__contains=[self.spec.config_id])
            )[0]
            hours_behind = (now - oldest_indicator.date_created).total_seconds() / (60 * 60)
            return int(1 + (hours_behind // 12)) * 12
        except IndexError:
            return None
