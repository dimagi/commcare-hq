import itertools
import pytz

PACT_DOMAIN = "pact"
PACT_HP_GROUPNAME = "PACT-HPS"
PACT_CASE_TYPE = 'cc_path_client'
PACT_SCHEDULES_NAMESPACE = 'pact_weekly_schedule'

PACT_DOTS_DATA_PROPERTY = "pact_dots_data_"
PACT_PROVIDERS_FIXTURE_CACHE_KEY = "CACHED_PACT_PROVIDERS_FIXTURES"

XMLNS_DOTS_FORM = "http://dev.commcarehq.org/pact/dots_form"
XMLNS_PROGRESS_NOTE = "http://dev.commcarehq.org/pact/progress_note"

XMLNS_PATIENT_UPDATE="http://dev.commcarehq.org/pact/patientupdate"
XMLNS_PATIENT_UPDATE_DOT="http://dev.commcarehq.org/pact/patientupdate_dot"
XMLNS_PATIENT_PROVIDER_UPDATE="http://dev.commcarehq.org/pact/patient_provider"

PACT_PROVIDER_FIXTURE_TAG = 'provider'

PACT_TIMEZONE = pytz.timezone('America/New_York')

DOT_NONART = "NONART"
DOT_NONART_IDX = 0

DOT_ART = "ART"
DOT_ART_IDX = 1

DOT_DAYS_INTERVAL = 21

CASE_ART_REGIMEN_PROP = 'artregimen'
CASE_NONART_REGIMEN_PROP = 'nonartregimen'

DOT_OBSERVATION_DIRECT = "direct" #saw them take it - most trustworthy
DOT_OBSERVATION_PILLBOX = "pillbox"
DOT_OBSERVATION_SELF = "self"

DOT_ADHERENCE_UNCHECKED = "unchecked" #not great
DOT_ADHERENCE_EMPTY = "empty" # good!
DOT_ADHERENCE_PARTIAL = "partial" #ok
DOT_ADHERENCE_FULL = "full" # bad - didn't take meds

DOT_UNCHECKED_CELL = (DOT_ADHERENCE_UNCHECKED, DOT_OBSERVATION_PILLBOX)


GENDER_CHOICES = (
    ('m', 'Male'),
    ('f', 'Female'),
    ('u', 'Undefined'),
    )
GENDER_CHOICES_DICT = dict(x for x in GENDER_CHOICES)

REGIMEN_CHOICES = {
    0: "None",
    1: "QD",
    2: "BID",
    3: "TID",
    4: "QID"
}


#old deprecated
#REGIMEN_CHOICES_DICT = dict(x for x in REGIMEN_CHOICES)

#http://confluence.dimagi.com/display/pactsbir/Technical+Specs
DAY_SLOTS_BY_TIME = {
    'morning': 0,
    'noon': 1,
    'evening': 2,
    'bedtime': 3,
    }


DAY_SLOTS_BY_IDX = {
    0: 'morning',
    1: 'noon',
    2: 'evening',
    3: 'bedtime',
    }

PACT_HP_CHOICES = (
#    ('HP', 'HP - Health Promoter (old)'),
    ('HP1', 'Health Promoter 1 (HP-1)'),
    ('HP2', 'Health Promoter 2 (HP-2)'),
    ('HP3', 'Health Promoter 3 (HP-3)'),
    ('Discharged', 'Discharged'),
    )
PACT_HP_CHOICES_DICT = dict(x for x in PACT_HP_CHOICES)

PACT_DOT_CHOICES = (
#    ('DOT', 'DOT - Directly Observed Therapy (old)'),
#    ('DOT7', 'Directly Observed Therapy 7 (DOT-7)'),
    ('DOT5', 'Directly Observed Therapy 5 (DOT-5)'),
    ('DOT3', 'Directly Observed Therapy 3 (DOT-3)'),
    ('DOT1', 'Directly Observed Therapy 1 (DOT-1)'),
    ('', 'No DOT'),
    )
PACT_DOT_CHOICES_DICT = dict(x for x in PACT_DOT_CHOICES)


PACT_REGIMEN_CHOICES = (
    ('None',[('', '-- None --'),]),
    ('QD - Once a day', [
        ('morning', 'Morning'),
        ('noon', 'Noon'),
        ('evening', 'Evening'),
        ('bedtime', 'Bedtime'),
        ]),
    ('BID - Twice a day', [
        ('morning,noon', 'Morning, Noon'),
        ('morning,evening', 'Morning, Evening'),
        ('morning,bedtime', 'Morning, Bedtime'),

        ('noon,evening', 'Noon, Evening'),
        ('noon,bedtime', 'Noon, Bedtime'),

        ('evening,bedtime', 'Evening, Bedtime'),
        ]),
    ('TID - Three times a day', [
        ('morning,noon,evening', 'Morning, Noon, Evening'),
        ('morning,noon,bedtime', 'Morning, Noon, Bedtime'),
        ('morning,evening,bedtime', 'Morning, Evening, Bedtime'),
        ('noon,evening,bedtime', 'Noon, Evening, Bedtime'),

        ]),
    ('QID - Four times a day', [
        ('morning,noon,evening,bedtime', 'Morning, Noon, Evening, Bedtime'),
        ]),
    )

PACT_REGIMEN_CHOICES_DICT = dict((x[0], dict(y for y in x[1])) for x in PACT_REGIMEN_CHOICES)
PACT_REGIMEN_CHOICES_FLAT_DICT = dict(x for x in itertools.chain(*[q[1] for q in PACT_REGIMEN_CHOICES]))

PACT_RACE_CHOICES = (
    ('white', 'White'),
    ('black-or-africanamerican', 'Black or African American'),
    ('asian', 'Asian'),
    ('american-indian-alaska-native', 'American Indian/Alaska Native'),
    ('more-than-one', 'More than one race'),
    ('unknown', 'Unknown or not reported'),
    )
PACT_RACE_CHOICES_DICT = dict(x for x in PACT_RACE_CHOICES)

PACT_LANGUAGE_CHOICES = (
    ('english', 'English'),
    ('spanish', 'Spanish'),
    ('haitian_creole', 'Haitian Creole'),
    ('portugese', 'Portugese'),
    )

PACT_LANGUAGE_CHOICES_DICT = dict(x for x in PACT_LANGUAGE_CHOICES)

PACT_HIV_CLINIC_CHOICES = (
    ("brigham_and_womens_hospital", "Brigham and Women's Hospital"),
    ("massachusetts_general_hospital", "Massachusetts General Hospital"),
    ("massachusetts_general_hospital_chelsea", "Massachusetts General Hospital - Chelsea"),
    ("massachusetts_general_hospital_charlestown", "Massachusetts General Hospital - Charlestown"),
    ("boston_healthcare_for_the_homeless_program", "Boston Healthcare for the Homeless Program"),
    ("beth_israel_deaconess_medical_center", "Beth Israel Deaconess Medical Center"),
    ("cambridge_health_alliance", "Cambridge Health Alliance - Zinberg Clinic"),
    ("cambridge_health_alliance_somerville", "Cambridge Health Alliance - Somerville"),
    ("cambridge_health_alliancewindsor_st", "Cambridge Health Alliance-Windsor St"),
    ("childrens_hospital", "Children's Hospital"),
    ("codman_square_health_center", "Codman Square Health Center"),
    ("dimock_center", "Dimock Center"),
    ("dorchester_house_multiservice_center", "Dorchester House Multi-Service Center"),
    ("east_boston_neighborhood_health_clinic", "East Boston Neighborhood Health Clinic"),
    ("faulkner_hospital", "Faulkner Hospital"),
    ("fenway_health_clinic", "Fenway Health Clinic"),
    ("harvard_vanguard_medical_associates", "Harvard Vanguard Medical Associates"),
    ("martha_eliot_health_center", "Martha Eliot Health Center"),
    ("tufts_medical_center", "Tufts Medical Center"),
    ("neponset_health_center", "Neponset Health Center"),
    ("lemuel_shattuck_hospital", "Lemuel Shattuck Hospital"),
    ("st_elizabeths_medical_center", "St. Elizabeth's Medical Center"),
    ("uphams_corner_health_center", "Upham's Corner Health Center"),
    ("boston_medical_center", "Boston Medical Center"),
    )
PACT_HIV_CLINIC_CHOICES_DICT = dict(x for x in PACT_HIV_CLINIC_CHOICES)

