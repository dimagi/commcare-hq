"""
PatientFinders are used to find OpenMRS patients that correspond to
CommCare cases if none of the patient identifiers listed in
OpenmrsCaseConfig.match_on_ids have successfully matched a patient.

See `README.md`__ for more context.
"""
import logging
from collections import namedtuple
from functools import partial
from pprint import pformat

from dimagi.ext.couchdbkit import (
    DecimalProperty,
    DictProperty,
    DocumentSchema,
    ListProperty,
)

from corehq.motech.finders import (
    MATCH_FUNCTIONS,
    PropertyWeight,
)
from corehq.motech.openmrs.const import OPENMRS_DATA_TYPE_BOOLEAN
from corehq.motech.value_source import (
    deserialize,
    recurse_subclasses,
)

logger = logging.getLogger(__name__)


constant_false = {
    "value": 'False',
    # We are fetching from a case property or a form question value, and
    # we want `get_value()` to return False (bool). `get_value()`
    # serialises case properties and form question values as external
    # data types. OPENMRS_DATA_TYPE_BOOLEAN is useful because it is a
    # bool, not a string, so `constant_false.get_value()` will return
    # False (not 'False')
    "external_data_type": OPENMRS_DATA_TYPE_BOOLEAN,
}


class PatientFinder(DocumentSchema):
    """
    The ``PatientFinder`` base class was developed as a way to
    handle situations where patient cases are created in CommCare
    instead of being imported from OpenMRS.

    When patients are imported from OpenMRS, they will come with at
    least one identifier that MOTECH can use to match the case in
    CommCare with the corresponding patient in OpenMRS. But if the case
    is registered in CommCare then we may not have an ID, or the ID
    could be wrong. We need to search for a corresponding OpenMRS
    patient.

    Different projects may focus on different kinds of case properties,
    so it was felt that a base class would allow some flexibility.

    The ``PatientFinder.wrap()`` method allows you to wrap documents of
    subclasses.

    The ``PatientFinder.find_patients()`` method must be implemented by
    subclasses. It returns a list of zero, one, or many patients. If it
    returns one patient, the OpenmrsRepeater.find_or_create_patient()
    will accept that patient as a true match.

    .. NOTE:: The consequences of a false positive (a Type II error) are
              severe: A real patient will have their valid values
              overwritten by those of someone else. So ``PatientFinder``
              subclasses should be written and configured to skew
              towards false negatives (Type I errors). In other words,
              it is much better not to choose a patient than to choose
              the wrong patient.

    """

    # Whether to create a new patient if no patients are found
    create_missing = DictProperty(default=constant_false)

    @classmethod
    def wrap(cls, data):
        if 'create_missing' in data and isinstance(data['create_missing'], bool):
            data['create_missing'] = {
                'external_data_type': OPENMRS_DATA_TYPE_BOOLEAN,
                'value': str(data['create_missing'])
            }

        if cls is PatientFinder:
            subclass = {
                sub._doc_type: sub for sub in recurse_subclasses(cls)
            }.get(data['doc_type'])
            return subclass.wrap(data) if subclass else None
        else:
            return super(PatientFinder, cls).wrap(data)

    def find_patients(self, requests, case, case_config):
        """
        Given a case, search OpenMRS for possible matches. Return the
        best results. Subclasses must define "best". If just one result
        is returned, it will be chosen.
        """
        raise NotImplementedError


PatientScore = namedtuple('PatientScore', ['patient', 'score'])


class WeightedPropertyPatientFinder(PatientFinder):
    """
    The ``WeightedPropertyPatientFinder`` class finds OpenMRS patients
    that match CommCare cases by assigning weights to case properties,
    and adding the weights of matching patient properties to calculate a
    confidence score.
    """

    # Identifiers that are searchable in OpenMRS. e.g.
    #     [ 'bahmni_id', 'household_id', 'last_name']
    searchable_properties = ListProperty()

    # The weight assigned to a matching property.
    # [
    #     {"case_property": "bahmni_id", "weight": 0.9},
    #     {"case_property": "household_id", "weight": 0.9},
    #     {
    #         "case_property": "dob",
    #         "weight": 0.75,
    #         "match_type": "days_diff",
    #         // days_diff matches based on days difference from given date
    #         "match_params": [364]
    #     },
    #     {
    #         "case_property": "first_name",
    #         "weight": 0.025,
    #         "match_type": "levenshtein",
    #         // levenshtein function takes edit_distance / len
    #         "match_params": [0.2]
    #         // i.e. 20% is one edit for every 5 characters
    #         // e.g. "Riyaz" matches "Riaz" but not "Riazz"
    #     },
    #     {"case_property": "last_name", "weight": 0.025},
    #     {"case_property": "municipality", "weight": 0.2},
    # ]
    property_weights = ListProperty(PropertyWeight)

    # The threshold that the sum of weights must pass for a CommCare case to
    # be considered a match to an OpenMRS patient
    threshold = DecimalProperty(default=1.0)

    # If more than one patient passes `threshold`, the margin by which the
    # weight of the best match must exceed the weight of the second-best match
    # to be considered correct.
    confidence_margin = DecimalProperty(default=0.667)  # Default: Matches two thirds better than second-best

    def __init__(self, *args, **kwargs):
        super(WeightedPropertyPatientFinder, self).__init__(*args, **kwargs)
        self._property_map = {}

    def get_score(self, patient, case):
        """
        Return the sum of weighted properties to give an OpenMRS
        patient a score of how well they match a CommCare case.
        """
        def weights():
            for property_weight in self.property_weights:
                prop = property_weight['case_property']
                jsonpath, value_source_dict = self._property_map[prop]
                weight = property_weight['weight']

                matches = jsonpath.find(patient)
                for match in matches:
                    patient_value = match.value
                    case_value = case.get_case_property(prop)
                    match_type = property_weight['match_type']
                    match_params = property_weight['match_params']
                    match_function = partial(MATCH_FUNCTIONS[match_type], *match_params)
                    is_equivalent = match_function(deserialize(value_source_dict, patient_value), case_value)
                    yield weight if is_equivalent else 0

        return sum(weights())

    def find_patients(self, requests, case, case_config):
        """
        Matches cases to patients. Returns a list of patients, each
        with a confidence score >= self.threshold
        """
        from corehq.motech.openmrs.openmrs_config import get_property_map
        from corehq.motech.openmrs.repeater_helpers import search_patients

        self._property_map = get_property_map(case_config)

        candidates = {}  # key on OpenMRS UUID to filter duplicates
        for prop in self.searchable_properties:
            value = case.get_case_property(prop)
            if value:
                response_json = search_patients(requests, value)
                for patient in response_json['results']:
                    score = self.get_score(patient, case)
                    if score >= self.threshold:
                        candidates[patient['uuid']] = PatientScore(patient, score)
        if not candidates:
            logger.info(
                'Unable to match case "%s" (%s): No candidate patients found.',
                case.name, case.get_id,
            )
            return []
        if len(candidates) == 1:
            patient = list(candidates.values())[0].patient
            logger.info(
                'Matched case "%s" (%s) to ONLY patient candidate: \n%s',
                case.name, case.get_id, pformat(patient, indent=2),
            )
            return [patient]
        patients_scores = sorted(candidates.values(), key=lambda candidate: candidate.score, reverse=True)
        if patients_scores[0].score / patients_scores[1].score > 1 + self.confidence_margin:
            # There is more than a `confidence_margin` difference
            # (defaults to 66.7%) in score between the best-ranked
            # patient and the second-best-ranked patient. Let's go with
            # Patient One.
            patient = patients_scores[0].patient
            logger.info(
                'Matched case "%s" (%s) to BEST patient candidate: \n%s',
                case.name, case.get_id, pformat(patients_scores, indent=2),
            )
            return [patient]
        # We can't be sure. Just send them all.
        logger.info(
            'Unable to match case "%s" (%s) to patient candidates: \n%s',
            case.name, case.get_id, pformat(patients_scores, indent=2),
        )
        return [ps.patient for ps in patients_scores]
