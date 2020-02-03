from memoized import memoized

from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.userreports.reports.util import ReportExport
from custom.inddex.filters import DateRangeFilter, GenderFilter, AgeRangeFilter, PregnancyFilter, \
    BreastFeedingFilter, SettlementAreaFilter, RecallStatusFilter, CaseOwnersFilter, \
    FaoWhoGiftFoodGroupDescriptionFilter, SupplementsFilter


class MultiSheetReportExport(ReportExport):

    def __init__(self, title, table_data):
        """
        Allows to export multitabular reports in one xmlns file, different report tables are
        presented as different sheets in document
        :param title: Exported file title
        :param table_data: list of tuples, first element of tuple is sheet title, second is list of rows
        """

        self.title = title
        self.table_data = table_data

    def build_export_data(self):
        sheets = []
        for name, rows in self.table_data:
            sheets.append([name, rows])
        return sheets

    @memoized
    def get_table(self):
        return self.build_export_data()


class MultiTabularReport(DatespanMixin, CustomProjectReport, GenericTabularReport):
    title = 'Multi report'
    name = 'Multi Report'
    slug = 'multi_report'
    report_template_path = 'inddex/multi_report.html'
    flush_layout = True
    default_rows = 10
    exportable = True

    @property
    def fields(self):
        return [CaseOwnersFilter, DateRangeFilter]

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.datespan.startdate,
            'enddate': self.datespan.enddate,
            'case_owners': self.case_owner
        }

    @property
    def case_owner(self):
        return self.request.GET.get('case_owners') or ''

    @property
    def data_providers(self):
        return []

    @property
    def report_context(self):
        return {
            'reports': [self.get_report_context(dp) for dp in self.data_providers],
            'title': self.title
        }

    @property
    @memoized
    def report_export(self):
        prepared_data = [self.format_table_to_export(dp) for dp in self.data_providers]
        return MultiSheetReportExport(self.title, prepared_data)

    @property
    def export_table(self):
        return self.report_export.get_table()

    def get_report_context(self, data_provider):
        self.data_source = data_provider
        if self.needs_filters:
            headers = []
            rows = []
        else:
            rows = data_provider.rows
            headers = data_provider.headers

        context = dict(
            report_table=dict(
                title=data_provider.title,
                slug=data_provider.slug,
                headers=headers,
                rows=rows
            )
        )

        return context

    def format_table_to_export(self, data_provider):
        exported_rows = [[header.html for header in data_provider.headers]]
        exported_rows.extend(data_provider.rows)
        title = data_provider.slug

        return title, exported_rows


class BaseNutrientReport(MultiTabularReport):

    @property
    def fields(self):
        return super().fields + [
            GenderFilter,
            AgeRangeFilter,
            PregnancyFilter,
            BreastFeedingFilter,
            SettlementAreaFilter,
            SupplementsFilter,
            RecallStatusFilter
        ]

    @property
    def filters_config(self):
        request_slugs = [
            'gender',
            'age_range',
            'pregnant',
            'breastfeeding',
            'urban_rural',
            'supplements',
            'recall_status',
        ]
        filters_config = super().report_config
        filters_config.update({slug: self.request.GET.get(slug, '') for slug in request_slugs})

        return filters_config
