from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.motech.openmrs.finders import PatientFinder
from dimagi.ext.couchdbkit import (
    DictProperty,
    DocumentSchema,
    ListProperty,
    SchemaDictProperty,
    SchemaListProperty,
    SchemaProperty,
    StringProperty,
)


def recurse_subclasses(cls):
    return (
        cls.__subclasses__() +
        [subsub for sub in cls.__subclasses__() for subsub in recurse_subclasses(sub)]
    )


class IdMatcher(DocumentSchema):
    case_property = StringProperty()
    identifier_type_id = StringProperty()


class ValueSource(DocumentSchema):
    @classmethod
    def wrap(cls, data):
        if cls is ValueSource:
            return {
                sub._doc_type: sub for sub in recurse_subclasses(cls)
            }[data['doc_type']].wrap(data)
        else:
            return super(ValueSource, cls).wrap(data)

    def get_value(self, case_trigger_info):
        raise NotImplementedError()


class CaseProperty(ValueSource):
    # Example "person_property" value::
    #
    #     {
    #       "birthdate": {
    #         "doc_type": "CaseProperty",
    #         "case_property": "dob"
    #       }
    #     }
    #
    case_property = StringProperty()

    def get_value(self, case_trigger_info):
        return case_trigger_info.updates.get(self.case_property)


class FormQuestion(ValueSource):
    form_question = StringProperty()  # e.g. "/data/foo/bar"

    def get_value(self, case_trigger_info):
        return case_trigger_info.form_question_values.get(self.form_question)


class ConstantString(ValueSource):
    # Example "person_property" value::
    #
    #     {
    #       "birthdate": {
    #         "doc_type": "ConstantString",
    #         "value": "Sep 7, 3761 BC"
    #       }
    #     }
    #
    value = StringProperty()

    def get_value(self, case_trigger_info):
        return self.value


class CasePropertyMap(CaseProperty):
    """
    Maps case property values to OpenMRS values or concept UUIDs
    """
    # Example "person_attribute" value::
    #
    #     {
    #       "00000000-771d-0000-0000-000000000000": {
    #         "doc_type": "CasePropertyMap",
    #         "case_property": "pill"
    #         "value_map": {
    #           "red": "00ff0000-771d-0000-0000-000000000000",
    #           "blue": "000000ff-771d-0000-0000-000000000000",
    #         }
    #       }
    #     }
    #
    value_map = DictProperty()

    def get_value(self, case_trigger_info):
        value = super(CasePropertyMap, self).get_value(case_trigger_info)
        try:
            return self.value_map[value]
        except KeyError:
            # We don't care if some CommCare answers are not mapped to OpenMRS concepts, e.g. when only the "yes"
            # value of a yes-no question in CommCare is mapped to a concept in OpenMRS.
            return None


class FormQuestionMap(FormQuestion):
    """
    Maps form question values to OpenMRS values or concept UUIDs
    """
    value_map = DictProperty()

    def get_value(self, case_trigger_info):
        value = super(FormQuestionMap, self).get_value(case_trigger_info)
        try:
            return self.value_map[value]
        except KeyError:
            return None


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
    #         {"case_property": "family_name", "weight": 0.4},
    #         {"case_property": "given_name", "weight": 0.3},
    #         {"case_property": "city", "weight": 0.2},
    #         {"case_property": "dob", "weight": 0.3}
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
