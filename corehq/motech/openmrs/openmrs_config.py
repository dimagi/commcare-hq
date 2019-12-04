from itertools import chain
from operator import eq

from jsonpath_rw import Child, Fields, Slice, Union, Where
from jsonpath_rw import parse as parse_jsonpath

from casexml.apps.case.models import (
    INDEX_RELATIONSHIP_CHILD,
    INDEX_RELATIONSHIP_EXTENSION,
)
from corehq.form_processor.abstract_models import DEFAULT_PARENT_IDENTIFIER
from dimagi.ext.couchdbkit import (
    DictProperty,
    DocumentSchema,
    ListProperty,
    SchemaDictProperty,
    SchemaListProperty,
    SchemaProperty,
    StringProperty,
)

from corehq.motech.openmrs.const import OPENMRS_PROPERTIES
from corehq.motech.openmrs.finders import PatientFinder
from corehq.motech.openmrs.jsonpath import Cmp, WhereNot

INDEX_RELATIONSHIPS = (
    INDEX_RELATIONSHIP_CHILD,
    INDEX_RELATIONSHIP_EXTENSION,
)

class OpenmrsCaseConfig(DocumentSchema):

    # "patient_identifiers": {
    #     "e2b966d0-1d5f-11e0-b929-000c29ad1d07": {
    #         "case_property": "nid"
    #     },
    #     "uuid": {
    #         "case_property": "openmrs_uuid",
    #     }
    # }
    patient_identifiers = DictProperty()

    # The patient_identifiers that are considered reliable
    # "match_on_ids": ["uuid", "e2b966d0-1d5f-11e0-b929-000c29ad1d07",
    match_on_ids = ListProperty()

    # "person_properties": {
    #     "gender": {
    #         "case_property": "gender"
    #     },
    #     "birthdate": {
    #         "case_property": "dob"
    #     }
    # }
    person_properties = DictProperty()

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
    #         "case_property": "given_name"
    #     },
    #     "middleName": {
    #         "case_property": "middle_name"
    #     },
    #     "familyName": {
    #         "case_property": "family_name"
    #     }
    # }
    person_preferred_name = DictProperty()

    # "person_preferred_address": {
    #     "address1": {
    #         "case_property": "address_1"
    #     },
    #     "address2": {
    #         "case_property": "address_2"
    #     },
    #     "cityVillage": {
    #         "case_property": "city"
    #     }
    # }
    person_preferred_address = DictProperty()

    # "person_attributes": {
    #     "c1f4239f-3f10-11e4-adec-0800271c1b75": {
    #         "case_property": "caste"
    #     },
    #     "c1f455e7-3f10-11e4-adec-0800271c1b75": {
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
    person_attributes = DictProperty()

    @classmethod
    def wrap(cls, data):
        if 'id_matchers' in data:
            # Convert legacy id_matchers to patient_identifiers. e.g.
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
        # Set default data types for known properties
        for property_, value_source in chain(
            data.get('person_properties', {}).items(),
            data.get('person_preferred_name', {}).items(),
            data.get('person_preferred_address', {}).items(),
        ):
            data_type = OPENMRS_PROPERTIES[property_]
            value_source.setdefault('external_data_type', data_type)
        return super(OpenmrsCaseConfig, cls).wrap(data)


class IndexedCaseMapping(DocumentSchema):
    identifier = StringProperty(required=True, default=DEFAULT_PARENT_IDENTIFIER)
    case_type = StringProperty(required=True)
    relationship = StringProperty(required=True, choices=INDEX_RELATIONSHIPS,
                                  default=INDEX_RELATIONSHIP_EXTENSION)

    # Sets case property values of a new extension case or child case.
    case_properties = ListProperty(required=True)


class ObservationMapping(DocumentSchema):
    """
    Maps OpenMRS Observations to value sources.

    e.g.::

        {
          "concept": "123456":
          "value": {
            "form_question": "/data/trimester"
            "value_map": {
              "first": "123456",
              "second": "123456",
              "third": "123456"
            },
            "direction": "out"
          }
        }

    """
    concept = StringProperty()
    value = DictProperty()

    # Import Observations as case updates from Atom feed. (Case type is
    # OpenmrsRepeater.white_listed_case_types[0]; Atom feed integration
    # requires len(OpenmrsRepeater.white_listed_case_types) == 1.)
    case_property = StringProperty(required=False)

    # Use indexed_case_mapping to create an extension case or a child
    # case instead of setting a case property. Used for referrals.
    indexed_case_mapping = SchemaProperty(
        IndexedCaseMapping, required=False, default=None, exclude_if_none=True
    )

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__)
            and other.concept == self.concept
            and other.value == self.value
            and other.case_property == self.case_property
        )


class OpenmrsFormConfig(DocumentSchema):
    xmlns = StringProperty()

    # Used to determine the start of a visit and an encounter. The end
    # of a visit is set to one day (specifically 23:59:59) later. If not
    # given, the value defaults to when the form was completed according
    # to the device, /meta/timeEnd.
    openmrs_start_datetime = DictProperty(required=False)

    openmrs_visit_type = StringProperty()
    openmrs_encounter_type = StringProperty()
    openmrs_form = StringProperty()
    openmrs_observations = ListProperty(ObservationMapping)
    bahmni_diagnoses = ListProperty(ObservationMapping)


class OpenmrsConfig(DocumentSchema):
    """
    Configuration for an OpenMRS repeater is stored in an
    ``OpenmrsConfig`` document.

    The ``case_config`` property maps CommCare case properties (mostly)
    to patient data, and uses the ``OpenmrsCaseConfig`` document schema.

    The ``form_configs`` property maps CommCare form questions (mostly)
    to event, encounter and observation data, and uses the
    ``OpenmrsFormConfig`` document schema.
    """
    openmrs_provider = StringProperty(required=False)
    case_config = SchemaProperty(OpenmrsCaseConfig)
    form_configs = ListProperty(OpenmrsFormConfig)


def get_property_map(case_config):
    """
    Returns a map of case properties to OpenMRS patient properties and
    attributes, and a value source dict to deserialize them.
    """
    property_map = {}

    for person_prop, value_source_dict in case_config['person_properties'].items():
        if 'case_property' in value_source_dict:
            jsonpath = parse_jsonpath('person.' + person_prop)
            property_map[value_source_dict['case_property']] = (jsonpath, value_source_dict)

    for attr_type_uuid, value_source_dict in case_config['person_attributes'].items():
        # jsonpath_rw offers programmatic JSONPath expressions. For details on how to create JSONPath
        # expressions programmatically see the
        # `jsonpath_rw documentation <https://github.com/kennknowles/python-jsonpath-rw#programmatic-jsonpath>`__
        #
        # The `Where` JSONPath expression "*jsonpath1* `where` *jsonpath2*" returns nodes matching *jsonpath1*
        # where a child matches *jsonpath2*. `Cmp` does a comparison in *jsonpath2*. It accepts a
        # comparison operator and a value. The JSONPath expression for matching simple attribute values is::
        #
        #     (person.attributes[*] where attributeType.uuid eq attr_type_uuid).value
        #
        # This extracts the person attribute values where their attribute type UUIDs match those configured in
        # case_config['person_attributes'].
        #
        # Person attributes with Concept values have UUIDs. The following JSONPath uses Union to match both simple
        # values and Concept values.
        if 'case_property' in value_source_dict:
            jsonpath = Union(
                # Simple values: Return value if it has no children.
                # (person.attributes[*] where attributeType.uuid eq attr_type_uuid).(value where not *)
                Child(
                    Where(
                        Child(Child(Fields('person'), Fields('attributes')), Slice()),
                        Cmp(Child(Fields('attributeType'), Fields('uuid')), eq, attr_type_uuid)
                    ),
                    WhereNot(Fields('value'), Fields('*'))
                ),
                # Concept values: Return value.uuid if value.uuid exists:
                # (person.attributes[*] where attributeType.uuid eq attr_type_uuid).value.uuid
                Child(
                    Where(
                        Child(Child(Fields('person'), Fields('attributes')), Slice()),
                        Cmp(Child(Fields('attributeType'), Fields('uuid')), eq, attr_type_uuid)
                    ),
                    Child(Fields('value'), Fields('uuid'))
                )
            )
            property_map[value_source_dict['case_property']] = (jsonpath, value_source_dict)

    for name_prop, value_source_dict in case_config['person_preferred_name'].items():
        if 'case_property' in value_source_dict:
            jsonpath = parse_jsonpath('person.preferredName.' + name_prop)
            property_map[value_source_dict['case_property']] = (jsonpath, value_source_dict)

    for addr_prop, value_source_dict in case_config['person_preferred_address'].items():
        if 'case_property' in value_source_dict:
            jsonpath = parse_jsonpath('person.preferredAddress.' + addr_prop)
            property_map[value_source_dict['case_property']] = (jsonpath, value_source_dict)

    for id_type_uuid, value_source_dict in case_config['patient_identifiers'].items():
        if 'case_property' in value_source_dict:
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
            property_map[value_source_dict['case_property']] = (jsonpath, value_source_dict)

    return property_map
