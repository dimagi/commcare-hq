from dimagi.utils.decorators.memoized import memoized
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.api.es import ReportCaseES
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard.cases.basic import CaseListReport


class MetReport(CustomProjectReport, CaseListReport):
    name = ugettext_noop("Conditions Met Report")
    slug = "met_report"

    fields = ['custom.opm.opm_reports.filters.SelectBlockFilter',
              'custom.opm.opm_reports.filters.AWCFilter',
              'corehq.apps.reports.filters.select.SelectOpenCloseFilter'
              ]

    @property
    @memoized
    def rendered_report_title(self):
        return self.name

    @property
    @memoized
    def case_es(self):
        return ReportCaseES(self.domain)

    @property
    def case_filter(self):
        return {}

    @property
    def headers(self):
        block = self.request_params.get('block', '')
        headers = DataTablesHeader(
                DataTablesColumn(_('List of Beneficiary')),
                DataTablesColumn(_('AWC Name')),
                DataTablesColumn(_("Month")),
                DataTablesColumn(_("Window")),
                DataTablesColumn(_("1")),
                DataTablesColumn(_("2")),
                DataTablesColumn(_("3")),
                DataTablesColumn(_("4")),
                DataTablesColumn(_("Cash to be transferred"))
        )

        if block.lower() == 'atri':
            headers.insert_column(DataTablesColumn(_("Husband Name")), 2)
            headers.insert_column(DataTablesColumn(_("5")), 9)
        elif block.lower() == 'wazirganj':
            headers.insert_column(DataTablesColumn(_("Current status")), 2)
        return headers

    @property
    def rows(self):
        return []

    @property
    def user_filter(self):
        return super(MetReport, self).user_filter