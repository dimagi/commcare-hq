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


# TODO Use below instead of HI_TYPES
class HealthInformationType:
    PRESCRIPTION = "Prescription"
    OP_CONSULTATION = "OPConsultation"
    DISCHARGE_SUMMARY = "DischargeSummary"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    IMMUNIZATION_RECORD = "ImmunizationRecord"
    HEALTH_DOCUMENT_RECORD = "HealthDocumentRecord"
    WELLNESS_RECORD = "WellnessRecord"
    CHOICES = [(PRESCRIPTION, 'Prescription'), (OP_CONSULTATION, 'OP Consultation'),
               (DISCHARGE_SUMMARY, 'Discharge Summary'), (DIAGNOSTIC_REPORT, 'Diagnostic Report'),
               (IMMUNIZATION_RECORD, 'Immunization Record'), (HEALTH_DOCUMENT_RECORD, 'Record artifact'),
               (WELLNESS_RECORD, 'Wellness Record')]


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


# Health Data Transfer Status
STATUS_ACKNOWLEDGED = 'ACKNOWLEDGED'
STATUS_TRANSFERRED = 'TRANSFERRED'
STATUS_DELIVERED = 'DELIVERED'
STATUS_FAILED = 'FAILED'
STATUS_ERRORED = 'ERRORED'


CRYPTO_ALGORITHM = 'ECDH'
CURVE = 'Curve25519'
AES_KEY_LENGTH = 32
NONCE_LENGTH = 32
HEALTH_INFORMATION_MEDIA_TYPE = 'application/fhir+json'
