import datetime

from memoized import memoized

from corehq.apps.reports.generic import GenericTabularReport
from corehq.apps.reports.standard import CustomProjectReport, DatespanMixin
from corehq.apps.userreports.reports.util import ReportExport
from custom.inddex.filters import DateRangeFilter, GenderFilter, AgeRangeFilter, PregnancyFilter, \
    BreastFeedingFilter, SettlementAreaFilter, RecallStatusFilter


class ReportBaseMixin:
    request = None

    @staticmethod
    def get_base_fields():
        return [
            GenderFilter,
            AgeRangeFilter,
            PregnancyFilter,
            BreastFeedingFilter,
            SettlementAreaFilter,
            RecallStatusFilter
        ]

    @staticmethod
    def get_base_report_config(obj):
        return {
            'gender': obj.gender,
            'age_range': obj.age_range,
            'pregnant': obj.pregnant,
            'breastfeeding': obj.breastfeeding,
            'urban_rural': obj.urban_rural,
            'supplements': obj.supplements,
            'recall_status': obj.recall_status
        }

    @property
    def age_range(self):
        return self.request.GET.get('age_range') or ''

    @property
    def gender(self):
        return self.request.GET.get('gender') or ''

    @property
    def urban_rural(self):
        return self.request.GET.get('urban_rural') or ''

    @property
    def breastfeeding(self):
        return self.request.GET.get('breastfeeding') or ''

    @property
    def pregnant(self):
        return self.request.GET.get('pregnant') or ''

    @property
    def supplements(self):
        return self.request.GET.get('supplements') or ''

    @property
    def recall_status(self):
        return self.request.GET.get('recall_status') or ''


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
    request = domain = None

    @property
    def fields(self):
        return [DateRangeFilter]

    @property
    def report_config(self):
        return {
            'domain': self.domain,
            'startdate': self.start_date,
            'enddate': self.end_date
        }

    @property
    def start_date(self):
        start_date = self.request.GET.get('startdate')

        return start_date if start_date else str(datetime.datetime.now().date())

    @property
    def end_date(self):
        end_date = self.request.GET.get('end_date')

        return end_date if end_date else str(datetime.datetime.now().date())

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
