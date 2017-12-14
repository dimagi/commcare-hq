from collections import OrderedDict

from corehq.motech.openmrs.finders import register_patient_finder, WeightedPropertyPatientFinder


@register_patient_finder
class PossibleHealthPatientFinder(WeightedPropertyPatientFinder):

    def __init__(self):
        super(PossibleHealthPatientFinder, self).__init__(
            searchable_properties=[
                'bahmni_id',
                'household_id',
                'last_name',
            ],
            property_weights=OrderedDict([
                ('bahmni_id', 0.9),
                ('household_id', 0.9),
                ('dob', 0.75),
                ('first_name', 0.025),
                ('last_name', 0.025),  # first_name + last_name = 5%
                ('municipality', 0.2),
            ]),
            threshold=1
        )
