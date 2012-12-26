from django.conf import settings
import itertools

PACT_DOMAIN = settings.PACT_DOMAIN
PACT_HP_GROUPNAME = settings.PACT_HP_GROUPNAME
PACT_HP_GROUP_ID = settings.PACT_HP_GROUP_ID
PACT_CASE_TYPE = 'cc_path_client' # WRONG is cc_path_type
PACT_SCHEDULES_NAMESPACE = 'pact_weekly_schedule'

PACT_DOTS_DATA_PROPERTY = "pact_dots_data_"

#Deprecated static sequence of time labels. needed to support legacy data pre labeling
TIME_LABEL_LOOKUP = (
    (),
    ('Dose',),
    ('Morning', 'Evening'),
    ('Morning', 'Noon', 'Evening'),
    ('Morning', 'Noon', 'Evening', 'Bedtime'),
    ('Dose', 'Morning', 'Noon', 'Evening', 'Bedtime'),
)

DOT_ART = "ART"
DOT_NONART = "NONART"

CASE_ART_REGIMEN_PROP = 'artregimen'
CASE_NONART_REGIMEN_PROP = 'nonartregimen'

DOT_OBSERVATION_DIRECT = "direct" #saw them take it - most trustworthy
DOT_OBSERVATION_PILLBOX = "pillbox"
DOT_OBSERVATION_SELF = "self"

DOT_ADHERENCE_UNCHECKED = "unchecked" #not great
DOT_ADHERENCE_EMPTY = "empty" # good!
DOT_ADHERENCE_PARTIAL = "partial" #ok
DOT_ADHERENCE_FULL = "full" # bad - didn't take meds



GENDER_CHOICES = (
    ('m', 'Male'),
    ('f', 'Female'),
    ('u', 'Undefined'),
    )
GENDER_CHOICES_DICT = dict(x for x in GENDER_CHOICES)

#deprecated
REGIMEN_CHOICES = (
    ('None', '-- No Regimen --'),
    (None, '-- No Regimen --'),
    ('QD', 'QD - Once a day'),
    ('BID', 'BID - Twice a day'),
    ('QD-AM', 'QD - Once a day (Morning)'),
    ('QD-PM', 'QD - Once a day (Evening)'),
    ('TID', 'TID - Three times a day'),
    ('QID', 'QID - Four times a day'),
    )

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
    ('DOT7', 'Directly Observed Therapy 7 (DOT-7)'),
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
    ("cambridge_health_alliance", "Cambridge Health Alliance"),
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

