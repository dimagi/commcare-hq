from custom.icds_reports.const import LocationTypes
from .prevalence_of_undernutrition_chart_data import PrevalenceOfUndernutritionChartData
from .prevalence_of_undernutrition_map_data import PrevalenceOfUndernutritionMapData
from .prevalence_of_undernutrition_sector_data import PrevalenceOfUndernutritionSectorData
from custom.icds_reports.utils import get_location_filter_value


def get_prevalence_of_undernutrition_report_data_instance(mode, domain, location_id, date, **kwargs):
    location_filter_value = get_location_filter_value(domain, location_id)
    if mode == 'map':
        if location_filter_value.location_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
            return PrevalenceOfUndernutritionSectorData(
                location_filter_value=location_filter_value,
                date=date,
                **kwargs
            )
        else:
            return PrevalenceOfUndernutritionMapData(
                location_filter_value=location_filter_value,
                date=date,
                **kwargs
            )
    elif mode == 'chart':
        return PrevalenceOfUndernutritionChartData(
            location_filter_value=location_filter_value,
            date=date,
            **kwargs
        )
    else:
        return None
