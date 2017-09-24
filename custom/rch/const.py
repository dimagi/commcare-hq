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

STATE_DISTRICT_MAPPING = {
    '28': [  # Andhra Pradesh
        '523'  # West Godavari
    ]
}

# meaningful mapping for integer record types in RCH
RCH_RECORD_TYPE_MAPPING = {
    MOTHER_RECORD_TYPE: 'mother',
    CHILD_RECORD_TYPE: 'child',
}
