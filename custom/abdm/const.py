ABHA_IN_USE_ERROR_CODE = 1001

ERROR_MESSAGES = {
    ABHA_IN_USE_ERROR_CODE: 'Provided ABHA is already linked to another beneficiary!'
}

SESSIONS_PATH = '/v0.5/sessions'
GATEWAY_CALLBACK_URL_PREFIX = 'api/gateway/v0.5'

CONSENT_PURPOSES = [('CAREMGT', 'Care Management'), ('BTG', 'Break the Glass'), ('PUBHLTH', 'Public Health'),
                    ('HPAYMT', 'Healthcare Payment'), ('DSRCH', 'Disease Specific Healthcare Research'),
                    ('PATRQT', 'Self Requested')]
CONSENT_PURPOSES_REF_URI = 'http://terminology.hl7.org/ValueSet/v3-PurposeOfUse'

HI_TYPES = [('OPConsultation', 'OP Consultation'), ('Prescription', 'Prescription'),
            ('DischargeSummary', 'Discharge Summary'), ('DiagnosticReport', 'Diagnostic Report'),
            ('ImmunizationRecord', 'Immunization Record'), ('HealthDocumentRecord', 'Record artifact'),
            ('WellnessRecord', 'Wellness Record')]

DATA_ACCESS_MODES = [(c, c) for c in ['VIEW', 'STORE', 'QUERY', 'STREAM']]
TIME_UNITS = [(c, c) for c in ['HOUR', 'WEEK', 'DAY', 'MONTH', 'YEAR']]

STATUS_PENDING = 'PENDING'
STATUS_REQUESTED = 'REQUESTED'
STATUS_GRANTED = 'GRANTED'
STATUS_DENIED = 'DENIED'
STATUS_ERROR = 'ERROR'
STATUS_REVOKED = 'REVOKED'
STATUS_EXPIRED = 'EXPIRED'

GATEWAY_CONSENT_STATUS_CHOICES = [(c, c) for c in [STATUS_GRANTED, STATUS_DENIED, STATUS_REVOKED,
                                                   STATUS_EXPIRED]]
