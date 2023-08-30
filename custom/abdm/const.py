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

STATUS_ACKNOWLEDGED = 'ACKNOWLEDGED'
STATUS_TRANSFERRED = 'TRANSFERRED'
STATUS_FAILED = 'FAILED'

GATEWAY_CONSENT_STATUS_CHOICES = [(c, c) for c in [STATUS_GRANTED, STATUS_DENIED, STATUS_REVOKED,
                                                   STATUS_EXPIRED]]


CRYPTO_ALGORITHM = 'ECDH'
CURVE = 'Curve25519'
AES_KEY_LENGTH = 32
NONCE_LENGTH = 32
HEALTH_INFORMATION_MEDIA_TYPE = 'application/fhir+json'
