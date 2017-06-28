from dimagi.ext.couchdbkit import *


class IdMatcher(DocumentSchema):
    case_property = StringProperty()
    identifier_type_id = StringProperty()


class ValueSource(DocumentSchema):
    @classmethod
    def wrap(cls, data):
        if cls is ValueSource:
            return {
                sub._doc_type: sub for sub in cls.__subclasses__()
            }[data['doc_type']].wrap(data)
        else:
            return super(ValueSource, cls).wrap(data)

    def get_value(self, case_trigger_info):
        raise NotImplementedError()


class CaseProperty(ValueSource):
    case_property = StringProperty()

    def get_value(self, case_trigger_info):
        return case_trigger_info.updates.get(self.case_property)


class ConstantString(ValueSource):
    value = StringProperty()

    def get_value(self, case_trigger_info):
        return self.value


class OpenmrsCaseConfig(DocumentSchema):
    id_matchers = SchemaListProperty(IdMatcher)
    person_properties = SchemaDictProperty(ValueSource)
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
    case_config = SchemaProperty(OpenmrsCaseConfig)
    form_configs = ListProperty(OpenmrsFormConfig)
