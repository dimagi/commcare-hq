from custom.world_vision.reports.child_report import ChildTTCReport
from custom.world_vision.reports.mixed_report import MixedTTCReport
from custom.world_vision.reports.mother_report import MotherTTCReport

DEFAULT_REPORT_CLASS = MixedTTCReport

WORLD_VISION_DOMAINS = ('wvindia2', )

CUSTOM_REPORTS = (
    ('TTC App Reports', (
        MixedTTCReport,
        MotherTTCReport,
        ChildTTCReport
    )),
)

REASON_FOR_CLOSURE_MAPPING = {
    'change_of_location': 'Migration',
    'end_of_care': 'End of care',
    'end_of_pregnancy': 'End of care (Postpartum Completed)',
    'not_pregnant': 'Not Pregnant (mostly  incorrect registrations)',
    'abortion': 'Abortion',
    'death': 'Death'
}

MOTHER_DEATH_MAPPING = {
    'seizure': 'Seizure or fits',
    'high_bp': 'High blood pressure',
    'bleeding_postpartum': 'Excessive bleeding post-delivery',
    'fever_or_infection_post_delivery': 'Fever or infection post-delivery',
    'during_caeserian_surgery': 'During Caeserian Surgery',
    'other': 'Other reason',
}

CHILD_DEATH_TYPE = {
    'newborn_death': 'Newborn deaths (< 1 month)',
    'infant_death': 'Infant deaths (< 1 year)',
    'child_death': 'Child deaths (> 1yr)'
}

CHILD_CAUSE_OF_DEATH = {
    'ari': 'ARI',
    'fever': 'Fever',
    'dysentery': 'Dysentery or diarrhea',
    'injury': 'Injury or accident',
    'malnutrition': 'Malnutrition',
    'cholera': 'Cholera',
    'measles': 'Measles',
    'meningitis': 'Meningitis',
    'other': 'Other',
}

FAMILY_PLANNING_METHODS = {
    'condom': 'Condom',
    'iud': 'IUD',
    'ocp': 'Contraceptive Pill',
    'injection': 'Depo-provera injection or implant',
    'permanent': 'Vasectomy or ligation',
    'natural': 'Natural methods',
    'other': 'Others',
    'not_wish_to_disclose': 'Does not wish to disclose'
}