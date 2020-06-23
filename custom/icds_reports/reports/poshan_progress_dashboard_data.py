from copy import deepcopy
from datetime import date

from django.db.models import Sum

from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import (
    PPR_HEADERS_COMPREHENSIVE,
    PPR_COLS_COMPREHENSIVE,
    PPR_COLS_TO_FETCH,
    PPR_COLS_PERCENTAGE_RELATIONS,
    PPD_ICDS_CAS_COVERAGE_OVERVIEW,
    PPD_SERVICE_DELIVERY_OVERVIEW,
    PPD_ICDS_CAS_COVERAGE_COMPARATIVE_MAPPING,
    PPD_SERVICE_DELIVERY_COMPARATIVE_MAPPING
)
from custom.icds_reports.models.views import PoshanProgressReportView
from custom.icds_reports.utils import apply_exclude, generate_quarter_months, calculate_percent, handle_average


def calculate_percentage_single_row(row, truncate_out=True):
    for k, v in PPR_COLS_PERCENTAGE_RELATIONS.items():
        num = row[v[0]]
        den = row[v[1]]
        extra_number = v[2] if len(v) > 2 else None
        row[k] = calculate_percent(num, den, extra_number, truncate_out)
        # calculation is done on decimal values
        # and then round off to nearest integer
        row[v[0]] = round(row[v[0]])
        row[v[1]] = round(row[v[1]])
    return row


def calculate_aggregated_row(data, aggregation_level, data_format):
    aggregated_row = {}
    # for quarter we need to average summation
    if data_format == 'quarter':
        for k, v in data.items():
            aggregated_row[k] = handle_average(v) if v else 0

    else:
        for k, v in data.items():
            aggregated_row[k] = v if v else 0

    aggregated_row = calculate_percentage_single_row(deepcopy(aggregated_row))
    # rounding values
    for col in ['num_launched_districts', 'num_launched_blocks', 'num_launched_states']:
        aggregated_row[col] = round(aggregated_row[col])
    aggregated_row = prepare_structure_aggregated_row(deepcopy(aggregated_row), aggregated_row['num_launched_states'],
                                                      aggregation_level)
    return aggregated_row


def prepare_structure_aggregated_row(row, count, aggregation_level):
    header_to_col_dict = dict(zip(PPR_HEADERS_COMPREHENSIVE, PPR_COLS_COMPREHENSIVE))
    icds_cas_coverage_overview = PPD_ICDS_CAS_COVERAGE_OVERVIEW[:]
    # for district level we don't need state count
    if aggregation_level == 2:
        icds_cas_coverage_overview.remove("Number of States Covered")
    icds_cas_coverage_dict = {}
    for key in icds_cas_coverage_overview:
        if key == "Number of States Covered":
            icds_cas_coverage_dict[key] = count
        else:
            icds_cas_coverage_dict[key] = row[header_to_col_dict[key]]
    service_delivery_overview = PPD_SERVICE_DELIVERY_OVERVIEW[:]
    service_delivery_dict = {}
    for key in service_delivery_overview:
        service_delivery_dict[key] = row[header_to_col_dict[key]]
    data = {
        "ICDS CAS Coverage": icds_cas_coverage_dict,
        "Service Delivery": service_delivery_dict
    }
    return data


def prepare_structure_comparative(data, aggregation_level):
    icds_cas_coverage_comparative_mapping = deepcopy(PPD_ICDS_CAS_COVERAGE_COMPARATIVE_MAPPING)
    icds_cas_coverage = []
    temp_array = []  # to add two indicators to one array (make frontend int. easy)
    for indicator, col in icds_cas_coverage_comparative_mapping.items():
        temp_array.append(get_top_worst_cases(deepcopy(data), col, aggregation_level, indicator))
        if len(temp_array) == 2:
            icds_cas_coverage.append(temp_array[:])
            temp_array = []
    service_delivery_comparative_mapping = deepcopy(PPD_SERVICE_DELIVERY_COMPARATIVE_MAPPING)
    temp_array = []
    service_delivery = []
    for indicator, col in service_delivery_comparative_mapping.items():
        temp_array.append(get_top_worst_cases(deepcopy(data), col, aggregation_level, indicator))
        if len(temp_array) == 2:
            service_delivery.append(temp_array[:])
            temp_array = []
    data = {
        "ICDS CAS Coverage": icds_cas_coverage,
        "Service Delivery": service_delivery
    }
    return data


def calculate_comparative_rows(data, aggregation_level, data_format, unique_id):
    # for quarter we need to average summation
    quarter_comparative_dict = {}
    if data_format == 'quarter':
        for i in range(0, len(data)):
            key = data[i][unique_id]
            if key not in quarter_comparative_dict.keys():
                quarter_comparative_dict[key] = data[i]
            else:
                for k, v in data[i].items():
                    if k not in ['state_name', 'district_name', unique_id]:
                        quarter_comparative_dict[key][k] += data[i][k] if data[i][k] else 0
                    else:
                        quarter_comparative_dict[key][k] = data[i][k]
        data = []
        for _, v in quarter_comparative_dict.items():
            data.append(v)

        for i in range(0, len(data)):
            for k, v in data[i].items():
                if k not in ['state_name', 'district_name', unique_id]:
                    data[i][k] = handle_average(v)
    response = []
    for i in range(0, len(data)):
        response.append(calculate_percentage_single_row(deepcopy(data[i]), False))
    response = prepare_structure_comparative(deepcopy(response), aggregation_level)
    return response


def get_top_worst_cases(data, key, aggregation_level, indicator_name):
    if aggregation_level == 1:
        place_key = "state_name"
    else:
        place_key = "district_name"
    worst_performers = sorted(data, key=lambda i: (i[key], i[PPR_COLS_PERCENTAGE_RELATIONS[key][1]]))
    best_performers = sorted(data, key=lambda i: (i[key], i[PPR_COLS_PERCENTAGE_RELATIONS[key][1]]), reverse=True)
    worst = []
    for per in worst_performers[:3]:
        worst.append({
            "place": per[place_key],
            "value": "{}%".format("%.2f" % per[key])
        })
    best = []
    for per in best_performers[:3]:
        best.append({
            "place": per[place_key],
            "value": "{}%".format("%.2f" % per[key])
        })
    ret = {
        "indicator": indicator_name,
        "Best performers": best,
        "Worst performers": worst
    }
    return ret


@icds_quickcache([
    'domain', 'location_filters', 'year', 'month', 'step', 'quarter', 'include_test'
], timeout=30 * 60)
def get_poshan_progress_dashboard_data(domain, year, month, quarter, data_format, step, location_filters,
                                       include_test=False):
    aggregation_level = location_filters.get('aggregation_level', 1)
    filters = location_filters
    value_fields = PPR_COLS_TO_FETCH[:]
    unique_id = ''
    if data_format == 'month':
        filters['month'] = date(year, month, 1)
    else:
        filters['month__in'] = generate_quarter_months(quarter, year)
        if aggregation_level == 1:
            unique_id = 'state_id'
            value_fields.append('state_id')
        else:
            unique_id = 'district_id'
            value_fields.append('district_id')
    order_by = ('state_name', 'district_name')
    if aggregation_level == 1:
        value_fields.remove('district_name')
    response = {}
    queryset = PoshanProgressReportView.objects.filter(**filters).order_by(*order_by)
    if not include_test:
        queryset = apply_exclude(domain, queryset)

    if step == 'aggregated':
        data = queryset.aggregate(
            num_launched_states=Sum('num_launched_states'),
            num_launched_districts=Sum('num_launched_districts'),
            num_launched_blocks=Sum('num_launched_blocks'),
            num_launched_awcs=Sum('num_launched_awcs'),
            awc_days_open=Sum('awc_days_open'),
            expected_visits=Sum('expected_visits'),
            valid_visits=Sum('valid_visits'),
            pse_eligible=Sum('pse_eligible'),
            pse_attended_21_days=Sum('pse_attended_21_days'),
            wer_eligible=Sum('wer_eligible'),
            wer_weighed=Sum('wer_weighed'),
            trimester_3=Sum('trimester_3'),
            counsel_immediate_bf=Sum('counsel_immediate_bf'),
            height_eligible=Sum('height_eligible'),
            height_measured_in_month=Sum('height_measured_in_month'),
            thr_eligible=Sum('thr_eligible'),
            thr_rations_21_plus_distributed=Sum('thr_rations_21_plus_distributed'),
            lunch_eligible=Sum('lunch_eligible'),
            lunch_count_21_days=Sum('lunch_count_21_days'),
        )
        response = calculate_aggregated_row(data, aggregation_level, data_format)
    elif step == 'comparative':
        data = queryset.values(*value_fields)
        response = calculate_comparative_rows(deepcopy(data), aggregation_level, data_format, unique_id)
    return response
