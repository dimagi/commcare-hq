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
)


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
    try:
        response = send_request_for_beneficiaries(for_date, state_id, beneficiary_type, district_id)
        data = response['_value_1'].find('NewDataSet')
        response_content = etree_to_dict(data)['NewDataSet']
        if (response_content[0].get('Table1', None) and
                response_content[0]['Table1'][0]['Message'] == 'Please check your URL or Security Code'):
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
