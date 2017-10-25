from custom.icds_reports.const import LocationTypes
from custom.icds_reports.reports.adhaar_data.adhaar_chart_data import AdhaarChartData
from custom.icds_reports.reports.adhaar_data.adhaar_map_data import AdhaarMapData
from custom.icds_reports.reports.adhaar_data.adhaar_sector_data import AdhaarSectorData
from custom.icds_reports.utils import get_location_filter_value


def get_adhaar_report_data_instance(mode, domain, location_id, date, **kwargs):
    location_filter_value = get_location_filter_value(domain, location_id)
    if mode == 'map':
        if location_filter_value.location_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
            return AdhaarSectorData(location_filter_value=location_filter_value, date=date, **kwargs)
        else:
            return AdhaarMapData(location_filter_value=location_filter_value, date=date, **kwargs)
    elif mode == 'chart':
        return AdhaarChartData(location_filter_value=location_filter_value, date=date, **kwargs)
    else:
        return None
