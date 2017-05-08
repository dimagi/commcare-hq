from collections import namedtuple

IdMatcher = namedtuple('IdMatcher', ['case_property', 'identifier_type'])


class Constructor(object):
    pass


class CaseProperty(Constructor):
    def __init__(self, case_property):
        self._case_property = case_property


class Constant(Constructor):
    def __init__(self, value):
        self._value = value


# http://fghomrsmpt.fgh.org.mz/openmrs/ws/rest/v1/patientidentifiertype/e2b966d0-1d5f-11e0-b929-000c29ad1d07
# http://fghomrsmpt.fgh.org.mz/openmrs/ws/rest/v1/patient?q={NID}&v=full
# | patient.indentifiers.*.identifier(identifier == NID && identifierType.uuid == {identifierTypeUUID})
id_matchers = [
    # "NID (SERVICO TARV)"
    IdMatcher(identifier_type_id='e2b966d0-1d5f-11e0-b929-000c29ad1d07', case_property='external_id'),
]

patient_mapping = {
    "person.gender": CaseProperty("genero"),
    "address1": CaseProperty("endereco_fisico"),
    "familyName": CaseProperty("apelido"),
    "givenName": CaseProperty("nome"),
    "middleName": Constant(""),
    "birthDate": CaseProperty("data_do_nacimento"),
}

person_attributes = {
    # http://fghomrsmpt.fgh.org.mz/openmrs/ws/rest/v1/personattributetype/e2e3fd64-1d5f-11e0-b929-000c29ad1d07
    'e2e3fd64-1d5f-11e0-b929-000c29ad1d07': CaseProperty("contact_phone_number")
}

# see also
# https://github.com/motech/modules/blob/650a7a851538b4bf2899a88f5ea07abc01d5ab70/
# openmrs/src/main/java/org/motechproject/openmrs/resource/impl/PersonResourceImpl.java
