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


class OpenmrsConfig(DocumentSchema):
    case_config = SchemaProperty(OpenmrsCaseConfig)


# http://fghomrsmpt.fgh.org.mz/openmrs/ws/rest/v1/patientidentifiertype/e2b966d0-1d5f-11e0-b929-000c29ad1d07
# http://fghomrsmpt.fgh.org.mz/openmrs/ws/rest/v1/patient?q={NID}&v=full
# | patient.indentifiers.*.identifier(identifier == NID && identifierType.uuid == {identifierTypeUUID})
id_matchers = [
    # "NID (SERVICO TARV)"
    IdMatcher(identifier_type_id='e2b966d0-1d5f-11e0-b929-000c29ad1d07', case_property='external_id'),
]

person_properties = {
    "gender": CaseProperty(case_property="genero"),
    "address1": CaseProperty(case_property="endereco_fisico"),
    "familyName": CaseProperty(case_property="apelido"),
    "givenName": CaseProperty(case_property="nome"),
    "middleName": ConstantString(value=""),
    "birthDate": CaseProperty(case_property="data_do_nacimento"),
}

person_attributes = {
    # http://fghomrsmpt.fgh.org.mz/openmrs/ws/rest/v1/personattributetype/e2e3fd64-1d5f-11e0-b929-000c29ad1d07
    'e2e3fd64-1d5f-11e0-b929-000c29ad1d07': CaseProperty(case_property="contact_phone_number")
}

# see also
# https://github.com/motech/modules/blob/650a7a851538b4bf2899a88f5ea07abc01d5ab70/
# openmrs/src/main/java/org/motechproject/openmrs/resource/impl/PersonResourceImpl.java
