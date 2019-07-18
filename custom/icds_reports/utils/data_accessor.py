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
from custom.icds_reports.models.views import NICIndicatorsView
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


# keeping cache timeout as 2 hours as this is going to be used
# in some script/tool which might flood us with requests
@icds_quickcache(['state_id', 'month'], timeout=120 * 60)
def get_inc_indicator_api_data(state_id, month):

    data = NICIndicatorsView.objects.get(month=month,
                                            state_id=state_id)

    # not using lxml because using lxml when no xml manipulation needed is just overengineering
    api_xml_response = """
    <?xml version="1.0" encoding="UTF-8"?>
    <SOAP-ENV:Envelope xmlns:SOAP-ENV="http://www.w3.org/2001/12/soap-envelope"
    SOAP-ENV:encodingStyle="http://www.w3.org/2001/12/soap-encoding">
       <SOAP-ENV:Header />
       <SOAP-ENV:Body>
          <state>{state_name}</state>
          <month>{month}</month>
          <num_launched_awcs>{num_launched_awcs}</num_launched_awcs>
          <num_households_registered>{cases_household}</num_households_registered>
          <pregnant_enrolled>{cases_ccs_pregnant}</pregnant_enrolled>
          <lactating_enrolled>{cases_ccs_lactating}</lactating_enrolled>
          <children_enrolled>{cases_child_health}</children_enrolled>
          <bf_at_birth>{bf_at_birth}</bf_at_birth>
          <ebf_in_month>{ebf_in_month}</ebf_in_month>
          <cf_in_month>{cf_in_month}</cf_in_month>
       </SOAP-ENV:Body>
    </SOAP-ENV:Envelope>
    """.format(
        state_name=data.state_name,
        month=data.month,
        num_launched_awcs=data.num_launched_awcs,
        cases_household=data.cases_household,
        cases_ccs_pregnant=data.cases_ccs_pregnant,
        cases_ccs_lactating=data.cases_ccs_lactating,
        cases_child_health=data.cases_child_health,
        bf_at_birth=data.bf_at_birth,
        ebf_in_month=data.ebf_in_month,
        cf_in_month=data.cf_initiation_in_month
    )

    return api_xml_response.strip()
