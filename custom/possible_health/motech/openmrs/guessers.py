from collections import OrderedDict

from corehq.motech.openmrs.guessers import (
    register_patient_guesser,
    PatientGuesserBase,
)


SEARCHABLE_PROPERTIES = [
    'bahmni_id',
    'household_id',
    'last_name',
]
PROPERTY_WEIGHTS = OrderedDict([
    ('bahmni_id', 0.9),
    ('household_id', 0.9),
    ('dob', 0.75),
    ('first_name', 0.025),
    ('last_name', 0.025),  # first_name + last_name = 5%
    ('municipality', 0.2),
])
THRESHOLD = 1


@register_patient_guesser
class PossibleHealthPatientGuesser(PatientGuesserBase):

    def __init__(self):
        self.property_map = {}

    def set_property_map(self, case_config)
        """
        Set self.property_map to map OpenMRS properties/attributes to
        case properties.
        """
        # TODO: ...
        pass

    def get_weight(self, patient, case):
        return sum(
            weight
            for prop, weight in PROPERTY_WEIGHTS.items()
            if patient[self.property_map[prop]] == case.get_case_property(prop)
        )

    def guess_patients(self, requests, case, case_config):
        """
        Matches cases to patients by iterating PROPERTY_WEIGHTS until
        a threshold of 1 is reached.
        """
        self.set_property_map(case_config)

        guesses = {}  # key on OpenMRS UUID to filter duplicates
        for prop in SEARCHABLE_PROPERTIES:
            value = case.get_case_property(prop)
            response = requests.get('/ws/rest/v1/patient', {'q': value, 'v': 'full'})
            for patient in response.json()['results']:
                if self.get_weight(patient, case) >= THRESHOLD:
                    guesses[patient['uuid']] = patient
        return guesses.values()
