from corehq.motech.openmrs.openmrs_config import IdMatcher, CaseProperty, ConstantString


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
# and more generally https://wiki.openmrs.org/display/docs/REST+Web+Service+Resources+in+OpenMRS+1.9
