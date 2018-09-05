"""
PatientFinders are used to find OpenMRS patients that correspond to
CommCare cases if none of the patient identifiers listed in
OpenmrsCaseConfig.match_on_ids have successfully matched a patient.

See `README.md`__ for more context.
"""
from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals

from collections import namedtuple
from functools import partial
from operator import eq
from pprint import pformat

import six
from jsonpath_rw import Child, parse, Fields, Slice, Where

from corehq.motech.openmrs.finders_utils import (
    le_days_diff,
    le_levenshtein_percent,
)
from corehq.motech.openmrs.jsonpath import Cmp
from corehq.motech.value_source import recurse_subclasses
from dimagi.ext.couchdbkit import (
    BooleanProperty,
    DecimalProperty,
    DocumentSchema,
    ListProperty,
    StringProperty,
)


MATCH_TYPE_EXACT = 'exact'
MATCH_TYPE_LEVENSHTEIN = 'levenshtein'  # Useful for words translated across alphabets
MATCH_TYPE_DAYS_DIFF = 'days_diff'  # Useful for estimated dates of birth
MATCH_FUNCTIONS = {
    MATCH_TYPE_EXACT: eq,
    MATCH_TYPE_LEVENSHTEIN: le_levenshtein_percent,
    MATCH_TYPE_DAYS_DIFF: le_days_diff,
}
MATCH_TYPES = tuple(MATCH_FUNCTIONS)
MATCH_TYPE_DEFAULT = MATCH_TYPE_EXACT


class PatientFinder(DocumentSchema):
    """
    Subclasses of the PatientFinder class implement particular
    strategies for finding OpenMRS patients that suit a particular
    project. (WeightedPropertyPatientFinder was first subclass to be
    written. A future project with stronger emphasis on patient names
    might use Levenshtein distance, for example.)

    Subclasses must implement the `find_patients()` method.
    """

    # If no patients are found, should a new one be created?
    create_missing = BooleanProperty(default=False)

    @classmethod
    def wrap(cls, data):

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
               return no results or multiple results than to return a
               single invalid result. Returned results should be
               logged.
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
    Used for updating _property_map to map case properties to OpenMRS
    patient property-, attribute- and concept values.

    i.e. Allows us to answer the question, "If we know the case property how
    do we find the OpenMRS value?"

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
    if value_source['doc_type'] == 'CasePropertyMap':
        value_map = {v: k for k, v in value_source['value_map'].items()}
        return {value_source['case_property']: JsonpathValuemap(jsonpath, value_map)}
    raise ValueError(
        '"{}" is not a recognised ValueSource for setting OpenMRS patient values from CommCare case properties. '
        'Please check your OpenMRS case config.'.format(value_source['doc_type'])
    )


PatientScore = namedtuple('PatientScore', ['patient', 'score'])


class PropertyWeight(DocumentSchema):
    case_property = StringProperty()
    weight = DecimalProperty()
    match_type = StringProperty(required=False, choices=MATCH_TYPES, default=MATCH_TYPE_DEFAULT)
    match_params = ListProperty(required=False)


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

    def set_property_map(self, case_config):
        """
        Set self._property_map to map OpenMRS properties and attributes
        to case properties.
        """
        # Example value of case_config::
        #
        #     {
        #         "person_properties": {
        #             "birthdate": {
        #                 "doc_type": "CaseProperty",
        #                 "case_property": "dob"
        #             }
        #         },
        #         "person_preferred_name": {
        #             "givenName": {
        #                 "doc_type": "CaseProperty",
        #                 "case_property": "given_name"
        #             },
        #             "familyName": {
        #                 "doc_type": "CaseProperty",
        #                 "case_property": "family_name"
        #             }
        #         },
        #         "person_preferred_address": {
        #             "address1": {
        #                 "doc_type": "CaseProperty",
        #                 "case_property": "address_1"
        #             },
        #             "address2": {
        #                 "doc_type": "CaseProperty",
        #                 "case_property": "address_2"
        #             }
        #         },
        #         "person_attributes": {
        #             "c1f4239f-3f10-11e4-adec-0800271c1b75": {
        #                 "doc_type": "CaseProperty",
        #                 "case_property": "caste"
        #             },
        #             "c1f455e7-3f10-11e4-adec-0800271c1b75": {
        #                 "doc_type": "CasePropertyMap",
        #                 "case_property": "class",
        #                 "value_map": {
        #                     "sc": "c1fcd1c6-3f10-11e4-adec-0800271c1b75",
        #                     "general": "c1fc20ab-3f10-11e4-adec-0800271c1b75",
        #                     "obc": "c1fb51cc-3f10-11e4-adec-0800271c1b75",
        #                     "other_caste": "c207073d-3f10-11e4-adec-0800271c1b75",
        #                     "st": "c20478b6-3f10-11e4-adec-0800271c1b75"
        #                 }
        #             }
        #         }
        #         // ...
        #     }
        #
        for person_prop, value_source in case_config['person_properties'].items():
            jsonpath = parse('person.' + person_prop)
            self._property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

        for attr_uuid, value_source in case_config['person_attributes'].items():
            # jsonpath_rw offers programmatic JSONPath expressions. For details on how to create JSONPath
            # expressions programmatically see the
            # `jsonpath_rw documentation <https://github.com/kennknowles/python-jsonpath-rw#programmatic-jsonpath>`__
            #
            # The `Where` JSONPath expression "*jsonpath1* `where` *jsonpath2*" returns nodes matching *jsonpath1*
            # where a child matches *jsonpath2*. `Cmp` does a comparison in *jsonpath2*. It accepts a
            # comparison operator and a value. The JSONPath expression below is the equivalent of::
            #
            #     (person.attributes[*] where attributeType.uuid eq attr_uuid).value
            #
            # This `for` loop will let us extract the person attribute values where their attribute type UUIDs
            # match those configured in case_config['person_attributes']
            jsonpath = Child(
                Where(
                    Child(Child(Fields('person'), Fields('attributes')), Slice()),
                    Cmp(Child(Fields('attributeType'), Fields('uuid')), eq, attr_uuid)
                ),
                Fields('value')
            )
            self._property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

        for name_prop, value_source in case_config['person_preferred_name'].items():
            jsonpath = parse('person.preferredName.' + name_prop)
            self._property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

        for addr_prop, value_source in case_config['person_preferred_address'].items():
            jsonpath = parse('person.preferredAddress.' + addr_prop)
            self._property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

        for id_type_uuid, value_source in case_config['patient_identifiers'].items():
            if id_type_uuid == 'uuid':
                jsonpath = parse('uuid')
            else:
                # The JSONPath expression below is the equivalent of::
                #
                #     (identifiers[*] where identifierType.uuid eq id_type_uuid).identifier
                #
                # Similar to `person_attributes` above, this will extract the person identifier values where
                # their identifier type UUIDs match those configured in case_config['patient_identifiers']
                jsonpath = Child(
                    Where(
                        Child(Fields('identifiers'), Slice()),
                        Cmp(Child(Fields('identifierType'), Fields('uuid')), eq, id_type_uuid)
                    ),
                    Fields('identifier')
                )
            self._property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

    def get_score(self, patient, case):
        """
        Return the sum of weighted properties to give an OpenMRS
        patient a score of how well they match a CommCare case.
        """
        def weights():
            for property_weight in self.property_weights:
                prop = property_weight['case_property']
                weight = property_weight['weight']

                matches = self._property_map[prop].jsonpath.find(patient)
                for match in matches:
                    patient_value = match.value
                    value_map = self._property_map[prop].value_map
                    case_value = case.get_case_property(prop)
                    match_type = property_weight['match_type']
                    match_params = property_weight['match_params']
                    match_function = partial(MATCH_FUNCTIONS[match_type], *match_params)
                    is_equivalent = match_function(value_map.get(patient_value, patient_value), case_value)
                    yield weight if is_equivalent else 0

        return sum(weights())

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
        patients_scores = sorted(six.itervalues(candidates), key=lambda candidate: candidate.score, reverse=True)
        if patients_scores[0].score / patients_scores[1].score > 1 + self.confidence_margin:
            # There is more than a `confidence_margin` difference
            # (defaults to 10%) in score between the best-ranked
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
