from django.utils.translation import ugettext as _
from django.utils.translation import ugettext_noop
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin, CustomProjectReport


class SystemOverviewReport(GenericTabularReport, CustomProjectReport, ProjectReportParametersMixin, DatespanMixin):
    slug = 'sys_overview'
    name = ugettext_noop("System Overview")
    description = ugettext_noop("Description for System Overview Report")
    section_name = ugettext_noop("System Overview")
    need_group_ids = True
    is_cacheable = True
    fields = [
        'corehq.apps.reports.fields.CombinedSelectUsersField',
        'corehq.apps.reports.fields.DatespanField',
    ]
    emailable = True

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(_("Sessions")),
            DataTablesColumn(_("Mobile Worker Messages")),
            DataTablesColumn(_("Case Messages")),
            DataTablesColumn(_("Incoming")),
            DataTablesColumn(_("Outgoing")),
        )

    @property
    def rows(self):
        return []