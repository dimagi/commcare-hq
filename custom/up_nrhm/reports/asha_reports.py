import calendar
from corehq.apps.reports.filters.select import YearFilter
from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.users.models import CommCareUser
from custom.up_nrhm.filters import DrillDownOptionFilter, SampleFormatFilter, ASHAMonthFilter,\
    NRHMDatespanFilter, NRHMDatespanMixin
from custom.up_nrhm.reports.asha_facilitators_report import ASHAFacilitatorsReport
from custom.up_nrhm.reports.asha_functionality_checklist_report import ASHAFunctionalityChecklistReport
from custom.up_nrhm.reports.block_level_af_report import BlockLevelAFReport
from custom.up_nrhm.reports.block_level_month_report import BlockLevelMonthReport
from custom.up_nrhm.reports.district_functionality_report import DistrictFunctionalityReport
from django.utils.translation import ugettext_lazy as _

def total_rows(report):
    if report.report_config.get('sf') == "sf2":
        return {
            "total_under_facilitator": getattr(report, 'total_under_facilitator', 0),
            "total_with_checklist": getattr(report, 'total_with_checklist', 0)
        }
    return {}


class ASHAReports(GenericTabularReport, NRHMDatespanMixin, CustomProjectReport):
    fields = [SampleFormatFilter, NRHMDatespanFilter, DrillDownOptionFilter, ASHAMonthFilter, YearFilter]
    name = _("ASHA Sangini Reports")
    slug = "asha_reports"
    show_all_rows = True
    default_rows = 20
    printable = True
    report_template_path = "up_nrhm/asha_report.html"
    extra_context_providers = [total_rows]
    no_value = '--'

    @property
    def report_subtitles(self):
        sf = self.report_config.get('sf')
        selected_af = self.request.GET.get('hierarchy_af')
        selected_block = self.request.GET.get('hierarchy_block')
        selected_district = self.request.GET.get('hierarchy_district')
        subtitles = [
            _("Selected Report: {0}".format(self.report.name)),
            _("Selected District: {0}".format(selected_district)),
        ]
        if not sf or sf in ['sf2', 'sf3', 'sf4']:
            subtitles.extend([
                _("Selected Block: {0}".format(selected_block)),
            ])
            if sf != 'sf4' and selected_af:
                user = CommCareUser.get(selected_af)
                subtitles.append(_("Selected AF: {0} {1}").format(user.first_name, user.last_name))

        if sf in ['sf5', 'sf4', 'sf3']:
            subtitles.append(
                _("Last Reporting Month of the Quarter: {0} {1}").format(
                    calendar.month_name[int(self.request.GET.get('month'))],
                    self.request.GET.get('year')
                )
            )
        else:
            subtitles.append(
                _("For Date: {0} to {1}").format(self.datespan.startdate.strftime("%Y-%m-%d"),
                                                 self.datespan.enddate.strftime("%Y-%m-%d"))
            )
        return subtitles


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
