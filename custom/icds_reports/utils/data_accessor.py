from __future__ import absolute_import
from __future__ import unicode_literals

from copy import deepcopy

from time import sleep

from corehq.util.datadog.utils import create_datadog_event
from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.const import LocationTypes
from custom.icds_reports.reports.awc_infrastracture import get_awc_infrastructure_data
from custom.icds_reports.reports.cas_reach_data import get_cas_reach_data
from custom.icds_reports.reports.demographics_data import get_demographics_data
from custom.icds_reports.reports.maternal_child import get_maternal_child_data
from custom.icds_reports.models.views import NICIndicatorsView
from custom.icds_reports.reports.awcs_covered import get_awcs_covered_data_map, get_awcs_covered_sector_data, \
    get_awcs_covered_data_chart

import logging

notify_logger = logging.getLogger('notify')


def _all_zeros(data, agg_level):
    values = [(not kpi['value'] and not kpi['all']) for row in data['records'] for kpi in row]
    retry = False
    if agg_level <= 1:
        retry = any(values)
    else:
        retry = all(values)
    if retry:
        create_datadog_event('ICDS 0s', 'All indicators in program summary equals 0', aggregation_key='icds_0')
    return retry


def get_program_summary_data(step, domain, config, now, include_test, pre_release_features):
    data = {}
    if step == 'maternal_child':
        data = get_maternal_child_data(domain, config, include_test, pre_release_features)
    elif step == 'icds_cas_reach':
        data = get_cas_reach_data(domain, now, config, include_test)
    elif step == 'demographics':
        data = get_demographics_data(domain, now, config, include_test, beta=pre_release_features)
    elif step == 'awc_infrastructure':
        data = get_awc_infrastructure_data(domain, config, include_test)
    return data


@icds_quickcache(['step', 'domain', 'config', 'now', 'include_test', 'pre_release_features'], timeout=30 * 60)
def get_program_summary_data_with_retrying(step, domain, config, now, include_test, pre_release_features):
    retry = 0
    while True:
        config_copy = deepcopy(config)
        aggregation_level = config_copy.get('aggregation_level')
        data = get_program_summary_data(step, domain, config_copy, now, include_test, pre_release_features)
        if not _all_zeros(data, aggregation_level) or retry == 2:
            break
        else:
            sleep(5)
            retry += 1
    return data


# keeping cache timeout as 2 hours as this is going to be used
# in some script/tool which might flood us with requests
@icds_quickcache(['state_id', 'month'], timeout=120 * 60)
def get_inc_indicator_api_data(state_id, month):

    data = NICIndicatorsView.objects.get(month=month,
                                         state_id=state_id)
    return {
        'state': data.state_name,
        'month': data.month,
        'num_launched_awcs': data.num_launched_awcs,
        'num_households_registered': data.cases_household,
        'pregnant_enrolled': data.cases_ccs_pregnant,
        'lactating_enrolled': data.cases_ccs_lactating,
        'children_enrolled': data.cases_child_health,
        'bf_at_birth': data.bf_at_birth,
        'ebf_in_month': data.ebf_in_month,
        'cf_in_month': data.cf_initiation_in_month
    }


def _all_zeros_graph(step, data, agg_level):
    if step == 'map':
        if agg_level <= 3:
            map_data_by_location = data['data']
        else:
            map_data_by_location = data['tooltips_data']

        values = [not all(map_data_by_location[key].values()) for key in map_data_by_location
                  if key not in ['original_name', 'fillKey']]
    else:
        values = [(not location['value']) for location in data['all_locations']]

    retry = all(values)
    if retry:
        create_datadog_event('ICDS 0s', 'All indicators in program summary equals 0', aggregation_key='icds_0')
    return retry


def get_awc_covered_data(step, domain, config, loc_level, location, include_test):
    if step == "map":
        if loc_level in [LocationTypes.SUPERVISOR, LocationTypes.AWC]:
            data = get_awcs_covered_sector_data(domain, config, loc_level, location, include_test)

        else:
            data = get_awcs_covered_data_map(domain, config.copy(), loc_level, include_test)

            if loc_level == LocationTypes.BLOCK:
                sector = get_awcs_covered_sector_data(
                    domain, config, loc_level, location, include_test
                )
                data.update(sector)
    elif step == "chart":
        data = get_awcs_covered_data_chart(domain, config, loc_level, include_test)
    return data


@icds_quickcache(['step', 'domain', 'config', 'loc_level', 'location', 'include_test'], timeout=30 * 60)
def get_awc_covered_data_with_retrying(step, domain, config, loc_level, location, include_test):
    retry = 0
    while True:
        config_copy = deepcopy(config)
        aggregation_level = config_copy.get('aggregation_level')
        data = get_awc_covered_data(step, domain, config_copy, loc_level, location, include_test)
        if not _all_zeros_graph(step, data, aggregation_level) or retry == 2:
            break
        else:
            sleep(5)
            retry += 1

    return data
