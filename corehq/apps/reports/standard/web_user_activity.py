from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop

from corehq.apps.reports.datatables import DataTablesColumn, DataTablesHeader
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReport


class WebUserActivityReport(GenericTabularReport, ProjectReport):
    slug = 'web_user_activity'
    name = ugettext_noop("Web User Activity")

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleUsername',
    ]

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Username")),
            DataTablesColumn(_("Activity")),
        )

    @property
    def rows(self):
        yield ['test1', 'downloaded something']
        yield ['test1', 'downloaded something']
        yield ['test1', 'exported something']
