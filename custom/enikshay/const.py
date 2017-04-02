# Case property names used in integrations
PRIMARY_PHONE_NUMBER = 'phone_number'
BACKUP_PHONE_NUMBER = 'secondary_contact_phone_number'

MERM_ID = 'merm_id'

PERSON_FIRST_NAME = 'first_name'
PERSON_LAST_NAME = 'last_name'

TREATMENT_START_DATE = 'treatment_initiation_date'
TREATMENT_SUPPORTER_FIRST_NAME = 'treatment_supporter_first_name'
TREATMENT_SUPPORTER_LAST_NAME = 'treatment_supporter_last_name'
TREATMENT_SUPPORTER_PHONE = 'treatment_supporter_mobile_number'

TREATMENT_OUTCOME = 'treatment_outcome'
TREATMENT_OUTCOME_DATE = 'treatment_outcome_date'
EPISODE_PENDING_REGISTRATION = "episode_pending_registration"
WEIGHT_BAND = 'weight_band'

CURRENT_ADDRESS = 'current_address'

NINETYNINEDOTS_PERSON_PROPERTIES = [
    PRIMARY_PHONE_NUMBER,
    BACKUP_PHONE_NUMBER,
    MERM_ID,
    PERSON_FIRST_NAME,
    PERSON_LAST_NAME,
    CURRENT_ADDRESS,
]
NINETYNINEDOTS_EPISODE_PROPERTIES = [
    TREATMENT_SUPPORTER_FIRST_NAME,
    TREATMENT_SUPPORTER_LAST_NAME,
    TREATMENT_SUPPORTER_PHONE,
    TREATMENT_OUTCOME,
    TREATMENT_OUTCOME_DATE,
    TREATMENT_START_DATE,
    WEIGHT_BAND,
]

DOSE_TAKEN_INDICATORS = [
    'directly_observed_dose',
    'unobserved_dose',
    'self_administered_dose',
]
