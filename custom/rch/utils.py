from zeep.client import Client
from requests.exceptions import HTTPError

from .emails import (
    notify_error_in_service,
    notify_insecure_access_response,
    notify_parsing_error,
)

from custom.rch.const import (
    PROJECTID,
    ID,
    PASSWORD,
    RCH_WSDL_URL,
    VALID_AADHAR_NUM_LENGTH,
    ICDS_CAS_DOMAIN,
    RCH_AUTHENTICATION_OR_NO_RESULT_ERROR_MESSAGE,
)
from custom.rch.exceptions import MultipleMatchException

from corehq.apps.es.case_search import CaseSearchES


def etree_to_dict(t):
    return {t.tag: map(etree_to_dict, t.iterchildren()) or t.text}


def send_request_for_beneficiaries(for_date, state_id, beneficiary_type, district_id):
    service_obj = _get_service()
    if not PROJECTID or not ID or not PASSWORD:
        raise NotImplementedError("You must set credentials for RCH API request")
    # need to pass the start and end date but since it would be the same we pass 'for_date' twice
    return service_obj(PROJECTID, ID, PASSWORD, for_date, for_date, state_id, beneficiary_type, district_id)


def _initiate_client():
    return Client(RCH_WSDL_URL)


def _get_service():
    return _initiate_client().service.DS_Data


def _fetch_beneficiaries(for_date, state_id, beneficiary_type, district_id):
    """
    Fetch beneficiaries of a specific type from RCH API for a certain date and district under a state.
    :param beneficiary_type: This can be any value from RCH_RECORD_TYPE_MAPPING keys
    """
    try:
        response = send_request_for_beneficiaries(for_date, state_id, beneficiary_type, district_id)
        data = response['_value_1'].find('NewDataSet')
        response_content = etree_to_dict(data)['NewDataSet']
        if (response_content[0].get('Table1', None) and
                response_content[0]['Table1'][0]['Message'] == RCH_AUTHENTICATION_OR_NO_RESULT_ERROR_MESSAGE):
            notify_insecure_access_response(for_date, state_id, beneficiary_type, district_id)
            return []
        return etree_to_dict(data)['NewDataSet']
    except HTTPError as e:
        notify_error_in_service(e.message, for_date)
        return []


def fetch_beneficiaries_records(for_date, state_id, beneficiary_type, district_id):
    records = _fetch_beneficiaries(for_date, state_id, beneficiary_type, district_id)
    try:
        return [record_data["Records"] for record_data in records]
    except ValueError:
        notify_parsing_error(for_date, state_id, beneficiary_type, district_id)
        return []


def valid_aadhar_num_length(aadhar_num):
    aadhar_num = str(aadhar_num)
    return len(aadhar_num) == VALID_AADHAR_NUM_LENGTH


def find_matching_cas_record_id(aadhar_num):
    query = (CaseSearchES().domain(ICDS_CAS_DOMAIN)
             .case_property_query("aadhar_number", aadhar_num, "must", fuzzy=False))
    hits = query.run().hits
    if len(hits) == 1:
        return hits[0].get('_id')
    elif len(hits) > 1:
        matching_case_ids = [hit.get('_id') for hit in hits]
        raise MultipleMatchException(
            """Multiple matches found for aadhar num: {aadhar_num}. Matched case_ids
            are {case_ids}""".format(aadhar_num=aadhar_num, case_ids=','.join(matching_case_ids))
        )
