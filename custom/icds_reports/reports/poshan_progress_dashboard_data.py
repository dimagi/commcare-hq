from copy import deepcopy
from datetime import date

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.views import PoshanProgressReportView
from custom.icds_reports.sqldata.exports.poshan_progress_report import (
    COLS_COMPREHENSIVE,
    COLS_TO_FETCH,
    COLS_PERCENTAGE_RELATIONS,
    HEADERS_COMPREHENSIVE,
    _generate_quarter_months,
    _calculate_percent, _handle_average
)
from custom.icds_reports.utils import apply_exclude

ICDS_CAS_COVERAGE_OVERVIEW = [
    "Number of States Covered", "Number of Districts Covered", "Number of Blocks Covered",
    "Number of AWCs Launched", "% Number of Days AWC Were opened", "% of Home Visits"]

SERVICE_DELIVERY_OVERVIEW = [
    "% of children between 3-6 years provided PSE for atleast 21+ days", "Weighing efficiency",
    "% of trimester three women counselled on immediate and EBF", "Height Measurement Efficiency",
    "% of children between 6 months -3 years, P&LW provided THR for atleast 21+ days",
    "% of children between 3-6 years provided SNP for atleast 21+ days"]

ICDS_CAS_COVERAGE_COMPARITIVE_MAPPING = {
    "AWC Open": "avg_days_awc_open_percent",
    "Home Visits": "visits_percent"
}
SERVICE_DELIVERY_COMPARITIVE_MAPPING = {
    "Pre-school Education": "pse_attended_21_days_percent",
    "Weighing efficiency": "weighed_percent",
    "Height Measurement Efficiency": "height_measured_in_month_percent",
    "Counselling": "counsel_immediate_bf_percent",
    "Take Home Ration": "thr_percent",
    "Supplementary Nutrition": "lunch_count_21_days_percent"
}


@icds_quickcache([
    'domain', 'location_filters', 'year', 'month', 'step', 'quarter', 'include_test'
], timeout=30 * 60)
def get_poshan_progress_dashboard_data(domain, year, month, quarter, data_format, step, location_filters,
                                       include_test=False):
    def calculate_percentage_single_row(row):
        for k, v in COLS_PERCENTAGE_RELATIONS.items():
            num = row[v[0]]
            den = row[v[1]]
            extra_number = v[2] if len(v) > 2 else None
            row[k] = _calculate_percent(num, den, extra_number)
        return row

    def calculate_aggregated_row(data, aggregation_level, data_format):
        aggregated_row = {}
        count = 0
        for row in data:
            count = count + 1  # count is used for number of states columns
            for k, v in row.items():
                if k not in aggregated_row.keys():
                    aggregated_row[k] = 0
                if k in ['state_name', 'district_name', 'district_id', 'state_id']:
                    aggregated_row[k] = v
                else:
                    aggregated_row[k] += v if v else 0
        # for quarter we need to average summation
        if data_format == 'quarter':
            for k, v in aggregated_row.items():
                if k not in ['state_name', 'district_name', 'district_id', 'state_id']:
                    aggregated_row[k] = _handle_average(v)
        aggregated_row = calculate_percentage_single_row(deepcopy(aggregated_row))
        aggregated_row = prepare_structure_aggregated_row(deepcopy(aggregated_row), count, aggregation_level)
        return aggregated_row

    def prepare_structure_aggregated_row(row, count, aggregation_level):
        header_to_col_dict = dict(zip(HEADERS_COMPREHENSIVE, COLS_COMPREHENSIVE))
        icds_cas_coverage_overview = ICDS_CAS_COVERAGE_OVERVIEW[:]
        # for district level we don't need state count
        if aggregation_level == 2:
            icds_cas_coverage_overview.remove("Number of States Covered")
        icds_cas_coverage_dict = {}
        for key in icds_cas_coverage_overview:
            if key == "Number of States Covered":
                icds_cas_coverage_dict[key] = count
            else:
                icds_cas_coverage_dict[key] = row[header_to_col_dict[key]]
        service_delivery_overview = SERVICE_DELIVERY_OVERVIEW[:]
        service_delivery_dict = {}
        for key in service_delivery_overview:
            service_delivery_dict[key] = row[header_to_col_dict[key]]
        data = {
            "ICDS CAS Coverage": icds_cas_coverage_dict,
            "Service Delivery": service_delivery_dict
        }
        return data

    def prepare_structure_comparative(data):
        icds_cas_coverage_comparitive_mapping = deepcopy(ICDS_CAS_COVERAGE_COMPARITIVE_MAPPING)
        icds_cas_coverage = []
        temp_array = [] # to add two indicators to one array (make frontend int. easy)
        for indicator, col in icds_cas_coverage_comparitive_mapping.items():
            temp_array.append(__get_top_worst_cases(deepcopy(data), col, aggregation_level, indicator))
            if len(temp_array) == 2:
                icds_cas_coverage.append(temp_array[:])
                temp_array = []
        service_delivery_comparitive_mapping = deepcopy(SERVICE_DELIVERY_COMPARITIVE_MAPPING)
        temp_array = []
        service_delivery = []
        for indicator, col in service_delivery_comparitive_mapping.items():
            temp_array.append(__get_top_worst_cases(deepcopy(data), col, aggregation_level, indicator))
            if len(temp_array) == 2:
                service_delivery.append(temp_array[:])
                temp_array = []
        data = {
            "ICDS CAS Coverage": icds_cas_coverage,
            "Service Delivery": service_delivery
        }
        return data

    def calculate_comparitive_rows(data, data_format, unique_id):
        # for quarter we need to average summation
        quarter_compartivie_dict = {}
        if data_format == 'quarter':
            for i in range(0, len(data)):
                if data[i][unique_id] in quarter_compartivie_dict.keys():
                    quarter_compartivie_dict[data[i][unique_id]] = data[i]
                else:
                    for k, v in data[i].items():
                        if v[unique_id] not in ['state_name', 'district_name', unique_id]:
                            quarter_compartivie_dict[v[unique_id]][k] += data[i][k] if data[i][k] else 0
                        else:
                            quarter_compartivie_dict[v[unique_id]][k] = data[i][k]
            data = []
            for _, v in quarter_compartivie_dict.items():
                data.append(v)

            for i in range(0, len(data)):
                for k, v in data[i].items():
                    if k not in ['state_name', 'district_name', unique_id]:
                        data[i][k] = _handle_average(v)
        response = []
        for i in range(0, len(data)):
            response.append(calculate_percentage_single_row(deepcopy(data[i])))
        response = prepare_structure_comparative(deepcopy(response))
        return response

    def __get_top_worst_cases(data, key, aggregation_level, indicator_name):

        if aggregation_level == 1:
            place_key = "state_name"
        else:
            place_key = "district_name"
        worst_performers = sorted(data, key=lambda i: i[key])
        best_performers = sorted(data, key=lambda i: i[key], reverse=True)
        worst = []
        for per in worst_performers[:3]:
            worst.append({
                "place": per[place_key],
                "value": per[key]
            })
        best = []
        for per in best_performers[:3]:
            best.append({
                "place": per[place_key],
                "value": per[key]
            })
        ret = {
            "indicator": indicator_name,
            "Best performers": best,
            "Worst performers": worst
        }
        return ret

    aggregation_level = location_filters.get('aggregation_level')
    filters = location_filters
    value_fields = COLS_TO_FETCH[:]
    unique_id = ''
    if data_format == 'month':
        filters['month'] = date(year, month, 1)
    else:
        filters['month__in'] = _generate_quarter_months(quarter, year)
        if aggregation_level == 1:
            unique_id = 'state_id'
            value_fields.append('state_id')
        else:
            unique_id = 'district_id'
            value_fields.append('district_id')
    order_by = ('state_name', 'district_name')
    if aggregation_level == 1:
        value_fields.remove('district_name')
    data = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by).values(*value_fields)
    if not include_test:
        data = apply_exclude(domain, data)
    aggregation_level = location_filters.get('aggregation_level')
    response = {}
    if step == 'aggregated':
        response = calculate_aggregated_row(data, aggregation_level, data_format)
    elif step == 'comparitive':
        response = calculate_comparitive_rows(deepcopy(data), aggregation_level, unique_id)
    return response
