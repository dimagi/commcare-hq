from zeep.client import Client
from requests.exceptions import HTTPError

from django.conf import settings
from .emails import (
    notify_error_in_service,
    notify_insecure_access_response,
    notify_parsing_error,
)


def etree_to_dict(t):
    return {t.tag: map(etree_to_dict, t.iterchildren()) or t.text}


PROJECTID = settings.RCH_CREDENTIALS.get('project_id')
ID = settings.RCH_CREDENTIALS.get('id')
PASSWORD = settings.RCH_CREDENTIALS.get('password')
MOTHER_RECORD_TYPE = '1'
CHILD_RECORD_TYPE = '2'

RCH_WSDL_URL = 'http://rchrpt.nhm.gov.in/RCH_WS/rchwebservices.svc?wsdl'


def send_request_for_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id):
    service_obj = _get_service()
    if not PROJECTID or not ID or not PASSWORD:
        raise NotImplementedError("You must set credentials for RCH API request")
    return service_obj(PROJECTID, ID, PASSWORD, from_date, to_date, state_id, beneficiary_type, district_id)


def _initiate_client():
    return Client(RCH_WSDL_URL)


def _get_service():
    return _initiate_client().service.DS_Data


def _fetch_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id):
    try:
        response = send_request_for_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id)
        data = response['_value_1'].find('NewDataSet')
        response_content = etree_to_dict(data)['NewDataSet']
        if (response_content[0].get('Table1', None) and
                response_content[0]['Table1'][0]['Message'] == 'Please check your URL or Security Code'):
            notify_insecure_access_response(from_date, state_id, beneficiary_type, district_id)
            return []
        return etree_to_dict(data)['NewDataSet']
    except HTTPError as e:
        notify_error_in_service(e.message, from_date)
        return []


def fetch_beneficiaries_records(from_date, to_date, state_id, beneficiary_type, district_id):
    records = _fetch_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id)
    try:
        return [record_data["Records"] for record_data in records]
    except ValueError:
        notify_parsing_error(from_date, state_id, beneficiary_type, district_id)
        return []
