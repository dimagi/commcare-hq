from __future__ import absolute_import
from __future__ import division

from collections import namedtuple
from pprint import pformat

from jsonpath_rw import parse

from dimagi.ext.couchdbkit import (
    DecimalProperty,
    DocumentSchema,
    ListProperty,
    StringProperty,
)


class PatientFinder(DocumentSchema):
    """
    PatientFinder is used to find a patient if ID matchers fail.
    """

    @classmethod
    def wrap(cls, data):
        from corehq.motech.openmrs.openmrs_config import recurse_subclasses

        if cls is PatientFinder:
            return {
                sub._doc_type: sub for sub in recurse_subclasses(cls)
            }[data['doc_type']].wrap(data)
        else:
            return super(PatientFinder, cls).wrap(data)

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


PatientScore = namedtuple('PatientScore', ['patient', 'score'])


class PropertyWeight(DocumentSchema):
    case_property = StringProperty()
    weight = DecimalProperty()


class WeightedPropertyPatientFinder(PatientFinder):
    """
    Finds patients that match cases by assigning weights to matching
    property values, and adding those weights to calculate a confidence
    score.
    """

    # Identifiers that are searchable in OpenMRS. e.g.
    #     [ 'bahmni_id', 'household_id', 'last_name']
    searchable_properties = ListProperty()

    # The weight assigned to a matching property.
    # [
    #     {"case_property": "bahmni_id", "weight": 0.9},
    #     {"case_property": "household_id", "weight": 0.9},
    #     {"case_property": "dob", "weight": 0.75},
    #     {"case_property": "first_name", "weight": 0.025},
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


    def __init__(self):
        super(WeightedPropertyPatientFinder, self).__init__()
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

    def save_match_id(self, case, case_config, patient):
        """
        If we are confident of the patient matched to a case, save
        the patient's ID to the case.
        """
        from casexml.apps.case.mock import CaseBlock
        from corehq.apps.hqcase.utils import submit_case_blocks

        id_map = {m['identifier_type_id']: m['case_property'] for m in case_config['id_matchers']}
        case_update = {}
        for identifier in patient['identifiers']:
            if identifier['identifierType']['uuid'] in id_map:
                case_property = id_map[identifier['identifierType']['uuid']]
                value = identifier['identifier']
                case_update[case_property] = value
        case_block = CaseBlock(
            case_id=case.get_id,
            create=False,
            update=case_update,
        )
        submit_case_blocks([case_block.as_string()], case.domain)

    def find_patients(self, requests, case, case_config):
        """
        Matches cases to patients. Returns a list of patients, each
        with a confidence score >= self.threshold
        """
        from corehq.motech.openmrs.logger import logger
        from corehq.motech.openmrs.repeater_helpers import search_patients

        self.set_property_map(case_config)

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
                'Unable to match case "%(case_name)s" (%(case_id)s): No candidate patients found.',
                case_name=case.name,
                case_id=case.get_id,
            )
            return []
        patients_scores = sorted(candidates.values(), key=lambda cand: cand.score, reverse=True)
        if len(patients_scores) == 1:
            patient = patients_scores[0].patient
            self.save_match_id(case, case_config, patient)
            logger.info(
                'Matched case "%(case_name)s" (%(case_id)s) to ONLY patient candidate: \n%(patient)s',
                case_name=case.name,
                case_id=case.get_id,
                patient=pformat(patient, indent=2),
            )
            return [patient]
        if patients_scores[0].score / patients_scores[1].score > 1 + self.confidence_margin:
            # There is more than a `confidence_margin` difference
            # (defaults to 10%) in score between the best-ranked
            # patient and the second-best-ranked patient. Let's go with
            # Patient One.
            patient = patients_scores[0].patient
            self.save_match_id(case, case_config, patient)
            logger.info(
                'Matched case "%(case_name)s" (%(case_id)s) to BEST patient candidate: \n%(patients)s',
                case_name=case.name,
                case_id=case.get_id,
                patient=pformat(patients_scores, indent=2),
            )
            return [patient]
        # We can't be sure. Just send them all.
        logger.info(
            'Unable to match case "%(case_name)s" (%(case_id)s) to patient candidates: \n%(patients)s',
            case_name=case.name,
            case_id=case.get_id,
            patient=pformat(patients_scores, indent=2),
        )
        return [ps.patient for ps in patients_scores]
