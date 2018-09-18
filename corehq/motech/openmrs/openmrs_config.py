from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.motech.openmrs.finders import PatientFinder
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
