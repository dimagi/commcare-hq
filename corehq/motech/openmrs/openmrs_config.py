from __future__ import absolute_import
from __future__ import unicode_literals

from collections import namedtuple
from operator import eq

from jsonpath_rw import Child, Fields, Slice, Where, parse as parse_jsonpath

from corehq.motech.openmrs.finders import PatientFinder
from corehq.motech.openmrs.jsonpath import Cmp
from corehq.motech.value_source import ValueSource
from dimagi.ext.couchdbkit import (
    DocumentSchema,
    ListProperty,
    SchemaDictProperty,
    SchemaProperty,
    StringProperty,
)


class IdMatcher(DocumentSchema):
    case_property = StringProperty()
    identifier_type_id = StringProperty()


class OpenmrsCaseConfig(DocumentSchema):

    # "patient_identifiers": {
    #     "e2b966d0-1d5f-11e0-b929-000c29ad1d07": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "nid"
    #     },
    #     "uuid": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "openmrs_uuid",
    #     }
    # }
    patient_identifiers = SchemaDictProperty(ValueSource)

    # The patient_identifiers that are considered reliable
    # "match_on_ids": ["uuid", "e2b966d0-1d5f-11e0-b929-000c29ad1d07",
    match_on_ids = ListProperty()

    # "person_properties": {
    #     "gender": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "gender"
    #     },
    #     "birthdate": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "dob"
    #     }
    # }
    person_properties = SchemaDictProperty(ValueSource)

    # "patient_finder": {
    #     "doc_type": "WeightedPropertyPatientFinder",
    #     "searchable_properties": ["nid", "family_name"],
    #     "property_weights": [
    #         {"case_property": "nid", "weight": 0.9},
    #         // if "match_type" is not given it defaults to "exact"
    #         {"case_property": "family_name", "weight": 0.4},
    #         {
    #             "case_property": "given_name",
    #             "weight": 0.3,
    #             "match_type": "levenshtein",
    #             // levenshtein function takes edit_distance / len
    #             "match_params": [0.2]
    #             // i.e. 0.2 (20%) is one edit for every 5 characters
    #             // e.g. "Riyaz" matches "Riaz" but not "Riazz"
    #         },
    #         {"case_property": "city", "weight": 0.2},
    #         {
    #             "case_property": "dob",
    #             "weight": 0.3,
    #             "match_type": "days_diff",
    #             // days_diff matches based on days difference from given date
    #             "match_params": [364]
    #         }
    #     ]
    # }
    patient_finder = PatientFinder(required=False)

    # "person_preferred_name": {
    #     "givenName": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "given_name"
    #     },
    #     "middleName": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "middle_name"
    #     },
    #     "familyName": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "family_name"
    #     }
    # }
    person_preferred_name = SchemaDictProperty(ValueSource)

    # "person_preferred_address": {
    #     "address1": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "address_1"
    #     },
    #     "address2": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "address_2"
    #     },
    #     "cityVillage": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "city"
    #     }
    # }
    person_preferred_address = SchemaDictProperty(ValueSource)

    # "person_attributes": {
    #     "c1f4239f-3f10-11e4-adec-0800271c1b75": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "caste"
    #     },
    #     "c1f455e7-3f10-11e4-adec-0800271c1b75": {
    #         "doc_type": "CasePropertyMap",
    #         "case_property": "class",
    #         "value_map": {
    #             "sc": "c1fcd1c6-3f10-11e4-adec-0800271c1b75",
    #             "general": "c1fc20ab-3f10-11e4-adec-0800271c1b75",
    #             "obc": "c1fb51cc-3f10-11e4-adec-0800271c1b75",
    #             "other_caste": "c207073d-3f10-11e4-adec-0800271c1b75",
    #             "st": "c20478b6-3f10-11e4-adec-0800271c1b75"
    #         }
    #     }
    # }
    person_attributes = SchemaDictProperty(ValueSource)

    @classmethod
    def wrap(cls, data):
        if 'id_matchers' in data:
            # Convert id_matchers to patient_identifiers. e.g.
            #     [{'doc_type': 'IdMatcher'
            #       'identifier_type_id': 'e2b966d0-1d5f-11e0-b929-000c29ad1d07',
            #       'case_property': 'nid'}]
            # to
            #     {'e2b966d0-1d5f-11e0-b929-000c29ad1d07': {'doc_type': 'CaseProperty', 'case_property': 'nid'}},
            patient_identifiers = {
                m['identifier_type_id']: {
                    'doc_type': 'CaseProperty',
                    'case_property': m['case_property']
                } for m in data['id_matchers']
            }
            data['patient_identifiers'] = patient_identifiers
            data['match_on_ids'] = list(patient_identifiers)
            data.pop('id_matchers')
        return super(OpenmrsCaseConfig, cls).wrap(data)


class ObservationMapping(DocumentSchema):
    concept = StringProperty()
    value = SchemaProperty(ValueSource)


class OpenmrsFormConfig(DocumentSchema):
    xmlns = StringProperty()
    openmrs_visit_type = StringProperty()
    openmrs_encounter_type = StringProperty()
    openmrs_form = StringProperty()
    openmrs_observations = ListProperty(ObservationMapping)


class OpenmrsConfig(DocumentSchema):
    openmrs_provider = StringProperty(required=False)
    case_config = SchemaProperty(OpenmrsCaseConfig)
    form_configs = ListProperty(OpenmrsFormConfig)


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


def get_property_map(case_config):
    """
    Returns a map of OpenMRS patient properties and attributes to case
    properties.
    """
    property_map = {}

    for person_prop, value_source in case_config['person_properties'].items():
        jsonpath = parse_jsonpath('person.' + person_prop)
        property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

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
        property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

    for name_prop, value_source in case_config['person_preferred_name'].items():
        jsonpath = parse_jsonpath('person.preferredName.' + name_prop)
        property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

    for addr_prop, value_source in case_config['person_preferred_address'].items():
        jsonpath = parse_jsonpath('person.preferredAddress.' + addr_prop)
        property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

    for id_type_uuid, value_source in case_config['patient_identifiers'].items():
        if id_type_uuid == 'uuid':
            jsonpath = parse_jsonpath('uuid')
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
        property_map.update(get_caseproperty_jsonpathvaluemap(jsonpath, value_source))

    return property_map
