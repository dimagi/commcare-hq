from custom.icds_reports.reports.abc.report_factory_abc import ReportFactoryABC
from custom.icds_reports.reports.adhaar_data.adhaar_chart_data import AdhaarChartData
from custom.icds_reports.reports.adhaar_data.adhaar_map_data import AdhaarMapData
from custom.icds_reports.reports.adhaar_data.adhaar_sector_data import AdhaarSectorData


class AdhaarReportFactory(ReportFactoryABC):

    def get_chart_report_instance(self, location_filter_value, date, **kwargs):
        return AdhaarChartData(location_filter_value=location_filter_value, date=date, **kwargs)

    def get_sector_report_instance(self, location_filter_value, date, **kwargs):
        return AdhaarSectorData(location_filter_value=location_filter_value, date=date, **kwargs)

    def get_map_report_instance(self, location_filter_value, date, **kwargs):
        return AdhaarMapData(location_filter_value=location_filter_value, date=date, **kwargs)
