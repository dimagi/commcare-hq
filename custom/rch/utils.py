from zeep.client import Client


def etree_to_dict(t):
    return {t.tag : map(etree_to_dict, t.iterchildren()) or t.text}


PROJECTID = ''  # From some secure place
ID = ''  # From some secure place
PASSWORD = ''  # From some secure place
MOTHER_DATA_TYPE = '1'
CHILD_DATA_TYPE = '2'

RCH_WSDL_URL = 'http://rchrpt.nhm.gov.in/RCH_WS/rchwebservices.svc?wsdl'


def send_request_for_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id):
    service_obj = _get_service()
    return service_obj(PROJECTID, ID, PASSWORD, from_date, to_date, state_id, beneficiary_type, district_id)


def _initiate_client():
    return Client(RCH_WSDL_URL)


def _get_service():
    return _initiate_client().service.DS_Data


def _fetch_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id):
    response = send_request_for_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id)
    data = response['_value_1'].find('NewDataSet')
    return etree_to_dict(data)['NewDataSet']


def fetch_beneficiaries_records(from_date, to_date, state_id, beneficiary_type, district_id):
    records = _fetch_beneficiaries(from_date, to_date, state_id, beneficiary_type, district_id)
    return [record_data["Records"] for record_data in records]
