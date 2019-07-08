from __future__ import absolute_import
from __future__ import unicode_literals

from copy import deepcopy

from time import sleep

from corehq.util.datadog.utils import create_datadog_event
from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.reports.awc_infrastracture import get_awc_infrastructure_data
from custom.icds_reports.reports.cas_reach_data import get_cas_reach_data
from custom.icds_reports.reports.demographics_data import get_demographics_data
from custom.icds_reports.reports.maternal_child import get_maternal_child_data
import logging

notify_logger = logging.getLogger('notify')


def _all_zeros(data):
    values = [(kpi['value'] == 0 and kpi['all'] == 0) for row in data['records'] for kpi in row]
    if all(values):
        create_datadog_event('ICDS 0s', 'All indicators in program summary equals 0')
    return all(values)


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
        data = get_program_summary_data(step, domain, config_copy, now, include_test, pre_release_features)
        if not _all_zeros(data) or retry == 2:
            break
        else:
            sleep(5)
            retry += 1
    return data
