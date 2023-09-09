GATEWAY_CALLBACK_URL_PREFIX = 'api/gateway/v0.5'
SESSIONS_PATH = '/v0.5/sessions'
HEALTH_INFORMATION_MEDIA_TYPE = 'application/fhir+json'

DATA_ACCESS_MODES = [(c, c) for c in ['VIEW', 'STORE', 'QUERY', 'STREAM']]
TIME_UNITS = [(c, c) for c in ['HOUR', 'WEEK', 'DAY', 'MONTH', 'YEAR']]


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


class ConsentPurpose:
    CARE_MANAGEMENT = 'CAREMGT'
    BREAK_THE_GLASS = 'BTG'
    PUBLIC_HEALTH = 'PUBHLTH'
    HEALTHCARE_PAYMENT = 'HPAYMT'
    DISEASE_SPECIFIC_HEALTHCARE_RESEARCH = 'DSRCH'
    SELF_REQUESTED = 'PATRQT'

    CHOICES = [(CARE_MANAGEMENT, 'Care Management'), (BREAK_THE_GLASS, 'Break the Glass'),
               (PUBLIC_HEALTH, 'Public Health'), (HEALTHCARE_PAYMENT, 'Healthcare Payment'),
               (DISEASE_SPECIFIC_HEALTHCARE_RESEARCH, 'Disease Specific Healthcare Research'),
               (SELF_REQUESTED, 'Self Requested')]

    REFERENCE_URI = 'http://terminology.hl7.org/ValueSet/v3-PurposeOfUse'


STATUS_PENDING = 'PENDING'
STATUS_REQUESTED = 'REQUESTED'
STATUS_GRANTED = 'GRANTED'
STATUS_DENIED = 'DENIED'
STATUS_ERROR = 'ERROR'
STATUS_REVOKED = 'REVOKED'
STATUS_EXPIRED = 'EXPIRED'

STATUS_ACKNOWLEDGED = 'ACKNOWLEDGED'
STATUS_TRANSFERRED = 'TRANSFERRED'
STATUS_DELIVERED = 'DELIVERED'
STATUS_FAILED = 'FAILED'
STATUS_ERRORED = 'ERRORED'
