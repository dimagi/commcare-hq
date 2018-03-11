from __future__ import absolute_import
from __future__ import unicode_literals
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
    case_property = StringProperty()

    def get_value(self, case_trigger_info):
        return case_trigger_info.updates.get(self.case_property)


class FormQuestion(ValueSource):
    form_question = StringProperty()  # e.g. "/data/foo/bar"

    def get_value(self, case_trigger_info):
        return case_trigger_info.form_question_values.get(self.form_question)


class ConstantString(ValueSource):
    value = StringProperty()

    def get_value(self, case_trigger_info):
        return self.value


class CasePropertyConcept(CaseProperty):
    """
    Maps case property values to OpenMRS concepts
    """
    value_concepts = DictProperty()

    def get_value(self, case_trigger_info):
        value = super(CasePropertyConcept, self).get_value(case_trigger_info)
        try:
            return self.value_concepts[value]
        except KeyError:
            # We don't care if some CommCare answers are not mapped to OpenMRS concepts, e.g. when only the "yes"
            # value of a yes-no question in CommCare is mapped to a concept in OpenMRS.
            return None


class FormQuestionConcept(FormQuestion):
    """
    Maps form question values to OpenMRS concepts
    """
    value_concepts = DictProperty()

    def get_value(self, case_trigger_info):
        value = super(FormQuestionConcept, self).get_value(case_trigger_info)
        try:
            return self.value_concepts[value]
        except KeyError:
            return None


class OpenmrsCaseConfig(DocumentSchema):
    id_matchers = SchemaListProperty(IdMatcher)
    person_properties = SchemaDictProperty(ValueSource)
    person_preferred_name = SchemaDictProperty(ValueSource)
    person_preferred_address = SchemaDictProperty(ValueSource)
    person_attributes = SchemaDictProperty(ValueSource)


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
