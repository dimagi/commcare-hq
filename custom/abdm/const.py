# TODO Consider moving to errors.py or inside hiu/hip
ABHA_IN_USE_ERROR_CODE = 1001

ERROR_MESSAGES = {
    ABHA_IN_USE_ERROR_CODE: 'Provided ABHA is already linked to another beneficiary!'
}

# TODO Consider moving to settings.py
X_CM_ID = 'sbx'     # sandbox consent manager id

ADDITIONAL_HEADERS = {'X-CM-ID': X_CM_ID}
SESSIONS_PATH = '/v0.5/sessions'

CONSENT_PURPOSES = [('CAREMGT', 'Care Management'), ('BTG', 'Break the Glass'), ('PUBHLTH', ''), ('HPAYMT', ''),
                    ('DSRCH', ''), ('PATRQT', '')]
HI_TYPES = [('OPConsultation', ''), ('Prescription', ''), ('DischargeSummary', ''), ('DiagnosticReport', ''),
            ('ImmunizationRecord', ''), ('HealthDocumentRecord', ''), ('WellnessRecord', '')]
DATA_ACCESS_MODES = [(c, c) for c in ['VIEW', 'STORE', 'QUERY', 'STREAM']]
TIME_UNITS = [(c, c) for c in ['HOUR', 'WEEK', 'DAY', 'MONTH', 'YEAR']]

STATUS_PENDING = 'PENDING'
STATUS_REQUESTED = 'REQUESTED'
STATUS_GRANTED = 'GRANTED'
STATUS_DENIED = 'DENIED'
STATUS_ERROR = 'ERROR'
STATUS_REVOKED = 'REVOKED'
STATUS_EXPIRED = 'EXPIRED'
GATEWAY_URL_PREFIX = 'api/gateway/v0.5'
