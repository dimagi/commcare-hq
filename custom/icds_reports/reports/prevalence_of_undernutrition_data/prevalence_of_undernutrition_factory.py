from custom.icds_reports.reports.abc.report_factory_abc import ReportFactoryABC
from .prevalence_of_undernutrition_chart_data import PrevalenceOfUndernutritionChartData
from .prevalence_of_undernutrition_map_data import PrevalenceOfUndernutritionMapData
from .prevalence_of_undernutrition_sector_data import PrevalenceOfUndernutritionSectorData


class PrevalanceOfUndernutritionReportFactory(ReportFactoryABC):

    def get_chart_report_instance(self, location_filter_value, date, **kwargs):
        return PrevalenceOfUndernutritionChartData(
            location_filter_value=location_filter_value,
            date=date,
            **kwargs
        )

    def get_sector_report_instance(self, location_filter_value, date, **kwargs):
        return PrevalenceOfUndernutritionSectorData(
            location_filter_value=location_filter_value,
            date=date,
            **kwargs
        )

    def get_map_report_instance(self, location_filter_value, date, **kwargs):
        return PrevalenceOfUndernutritionMapData(
            location_filter_value=location_filter_value,
            date=date,
            **kwargs
        )
