import json
import os
from django.conf import settings

PROJECTID = settings.RCH_CREDENTIALS.get('project_id')
ID = settings.RCH_CREDENTIALS.get('id')
PASSWORD = settings.RCH_CREDENTIALS.get('password')
MOTHER_RECORD_TYPE = '1'
CHILD_RECORD_TYPE = '2'
VALID_AADHAR_NUM_LENGTH = 12
AADHAR_NUM_FIELDS = ['Child_Aadhaar_No', 'PW_Aadhar_No', 'aadhar_num']
RCH_WSDL_URL = 'http://rchrpt.nhm.gov.in/RCH_WS/rchwebservices.svc?wsdl'
ICDS_CAS_DOMAIN = "icds-cas"
RECORDS_PER_PAGE = 200
# RCH returns same error message in case of no records or authentication failure
RCH_AUTHENTICATION_OR_NO_RESULT_ERROR_MESSAGE = "Please check your URL or Security Code"


STATE_DISTRICT_MAPPING = {
    '28': [  # Andhra Pradesh
        '523'  # West Godavari
    ]
}

# meaningful mapping for integer record types in RCH
RCH_RECORD_TYPE_MAPPING = {
    'mother': MOTHER_RECORD_TYPE,
    'child': CHILD_RECORD_TYPE
}

RCH_PERMITTED_FIELD_MAPPINGS = {
    'mother': json.load(open(os.path.join('custom', 'rch', 'all_fields', 'mother.json')))['fields'],
    'child': json.load(open(os.path.join('custom', 'rch', 'all_fields', 'child.json')))['fields']
}


def extract_rch_fields_from_mapping(beneficiary_type):
    field_mappings = RCH_PERMITTED_FIELD_MAPPINGS[beneficiary_type]
    rch_fields = []
    for case_type in field_mappings:
        rch_fields = rch_fields + field_mappings[case_type].keys()
    return rch_fields


RCH_PERMITTED_FIELDS = {
    'mother': extract_rch_fields_from_mapping('mother'),
    'child': extract_rch_fields_from_mapping('child'),
}
