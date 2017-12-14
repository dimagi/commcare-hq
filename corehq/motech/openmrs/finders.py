from __future__ import division
from collections import namedtuple

from jsonpath_rw import parse


PATIENT_FINDERS = []


def register_patient_finder(class_):
    PATIENT_FINDERS.append(class_)
    return class_


class PatientFinderBase(object):
    """
    PatientFinderBase is used to find a patient if ID matchers fail.
    """

    def find_patients(self, requests, case, case_config):
        """
        Given a case, search OpenMRS for possible matches. Return the
        best results. Subclasses must define "best". If just one result
        is returned, it will be chosen.

        NOTE:: False positives can result in overwriting one patient
               with the data of another. It is definitely better to
               return no results than to return an invalid result.
               Returned results should be logged.

        """
        raise NotImplementedError


# JsonpathValueMap is for comparing OpenMRS patients with CommCare
# cases.
#
# The `jsonpath` attribute is used for retrieving values from an
# OpenMRS patient and the `value_map` attribute is for converting
# OpenMRS concept UUIDs to CommCare property values, if necessary.
JsonpathValuemap = namedtuple('JsonpathValuemap', ['jsonpath', 'value_map'])


def get_caseproperty_jsonpathvaluemap(jsonpath, value_source):
    """
    Used for updating property_map to map case properties to OpenMRS
    patient property-, attribute- and concept values.

    :param jsonpath: The path to a value in an OpenMRS patient JSON object
    :param value_source: A case_config ValueSource instance
    :return: A single-item dictionary with the name of the case
             property as key, and a JsonpathValuemap as value. If
             value_source is a constant, then there is no corresponding
             case property, so the function returns an empty dictionary
    """
    if value_source['doc_type'] == 'ConstantString':
        return {}
    if value_source['doc_type'] == 'CaseProperty':
        return {value_source['case_property']: JsonpathValuemap(jsonpath, {})}
    if value_source['doc_type'] == 'CasePropertyConcept':
        value_map = {v: k for k, v in value_source['value_concepts'].items()}
        return {value_source['case_property']: JsonpathValuemap(jsonpath, value_map)}


class WeightedPropertyPatientFinder(PatientFinderBase):
    """
    Finds patients that match cases by assigning weights to matching
    property values, and adding those weights to calculate a confidence
    score.
    """
    def __init__(self, searchable_properties, property_weights, threshold=1, confidence_margin=0.1):
        """
        Initialise the instance

        :param searchable_properties: Properties that can be used to
               search for patients in OpenMRS
        :param property_weights: A dictionary of case property names
               and their weights
        :param threshold: The sum of weights that must be met in order
               for a patient to be considered a match
        """
        self.searchable_properties = searchable_properties
        self.property_weights = property_weights
        self.threshold = threshold
        self.confidence_margin = confidence_margin
        self.property_map = {}

    def set_property_map(self, case_config):
        """
        Set self.property_map to map OpenMRS properties and attributes
        to case properties.
        """
        # Example value of case_config::
        #
        #     {
        #       "person_properties": {
        #         "birthdate": {
        #           "doc_type": "CaseProperty",
        #           "case_property": "dob"
        #         }
        #       },
        #       // ...
        #     }
        #

        for person_prop, value_source in case_config['person_properties'].items():
            jsonpath = 'person.' + person_prop
            self.property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

        for attr_uuid, value_source in case_config['person_attributes'].items():
            jsonpath = 'person.attributes.value where `parent`.attributeType.uuid = "' + attr_uuid + '"'
            self.property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

        for name_prop, value_source in case_config['person_preferred_name'].items():
            jsonpath = 'person.preferredName.' + name_prop
            self.property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

        for addr_prop, value_source in case_config['person_preferred_address'].items():
            jsonpath = 'person.preferredAddress.' + addr_prop
            self.property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

    def get_score(self, patient, case):
        """
        Return the sum of weighted properties to give an OpenMRS
        patient a score of how well they match a CommCare case.
        """
        def weights():
            for prop, weight in self.property_weights.items():
                case_value = case.get_case_property(prop)
                jsonpath_expr = parse(self.property_map[prop].jsonpath)
                patient_value = jsonpath_expr.find(patient)
                value_map = self.property_map[prop].value_map
                is_equal = value_map.get(patient_value, patient_value) == case_value
                yield weight if is_equal else 0

        return sum(weights())

    def find_patients(self, requests, case, case_config):
        """
        Matches cases to patients. Returns a list of patients, each
        with a confidence score >= THRESHOLD
        """
        PatientScore = namedtuple('PatientScore', ['patient', 'score'])
        self.set_property_map(case_config)

        candidates = {}  # key on OpenMRS UUID to filter duplicates
        for prop in self.searchable_properties:
            value = case.get_case_property(prop)
            response = requests.get('/ws/rest/v1/patient', {'q': value, 'v': 'full'})
            for patient in response.json()['results']:
                score = self.get_score(patient, case)
                if score >= self.threshold:
                    candidates[patient['uuid']] = PatientScore(patient, score)
        if not candidates:
            return []
        patients_scores = sorted(candidates.values(), key=lambda cand: cand.score, reverse=True)
        if len(patients_scores) == 1:
            return [patients_scores[0].patient]
        if patients_scores[0].score / patients_scores[1].score > 1 + self.confidence_margin:
            # There is more than a `confidence_margin` difference
            # (defaults to 10%) in score between the best-ranked
            # patient and the second-best-ranked patient. Let's go with
            # Patient One.
            return [patients_scores[0].patient]
        # We can't be sure. Just send them all.
        return [ps.patient for ps in patients_scores]
