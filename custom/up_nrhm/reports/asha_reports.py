from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from custom.up_nrhm.filters import DrillDownOptionFilter, SampleFormatFilter, ASHAMonthFilter,\
    NRHMDatespanFilter, NRHMDatespanMixin
from custom.up_nrhm.reports.asha_facilitators_report import ASHAFacilitatorsReport
from custom.up_nrhm.reports.asha_functionality_checklist_report import ASHAFunctionalityChecklistReport
from custom.up_nrhm.reports.block_level_af_report import BlockLevelAFReport
from custom.up_nrhm.reports.block_level_month_report import BlockLevelMonthReport
from custom.up_nrhm.reports.district_functionality_report import DistrictFunctionalityReport


def total_rows(report):
    if report.report_config.get('sf') == "sf2":
        return {
            "total_under_facilitator": getattr(report, 'total_under_facilitator', 0),
            "total_with_checklist": getattr(report, 'total_with_checklist', 0)
        }
    return {}


class ASHAReports(GenericTabularReport, NRHMDatespanMixin, CustomProjectReport):
    fields = [SampleFormatFilter, NRHMDatespanFilter, DrillDownOptionFilter, ASHAMonthFilter, YearFilter]
    name = "ASHA Reports"
    slug = "asha_reports"
    show_all_rows = True
    default_rows = 20
    printable = True
    report_template_path = "up_nrhm/asha_report.html"
    extra_context_providers = [total_rows]
    no_value = '--'

    @property
    def report_config(self):
        config = {
            'sf': self.request.GET.get('sf'),
        }
        return config

    @property
    def report_context(self):
        context = super(ASHAReports, self).report_context
        context['sf'] = self.request.GET.get('sf')
        return context

    @property
    def report(self):
        config = self.report_config
        if config.get('sf') == 'sf5':
            return DistrictFunctionalityReport(self.request, domain=self.domain)
        elif config.get('sf') == 'sf4':
            return BlockLevelAFReport(self.request, domain=self.domain)
        elif config.get('sf') == 'sf3':
            return BlockLevelMonthReport(self.request, domain=self.domain)
        elif config.get('sf') == 'sf2':
            return ASHAFacilitatorsReport(self.request, domain=self.domain)
        else:
            return ASHAFunctionalityChecklistReport(self.request, domain=self.domain)


    @property
    def headers(self):
        return self.report.headers

    @property
    def rows(self):
        config = self.report_config
        if not config.get('sf'):
            rows = self.report.rows
        elif config.get('sf') == 'sf2':
            rows, self.total_under_facilitator, self.total_with_checklist = self.report.rows
        else:
            rows = self.report.rows[0]
        return rows
