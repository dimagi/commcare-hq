import jsonobject


class PatientIdentifierType(jsonobject.JsonObject):
    uuid = jsonobject.StringProperty()
    display = jsonobject.StringProperty()
    description = jsonobject.StringProperty()


def openmrs_patient_identifier_type_json_from_api_json(api_json):
    return PatientIdentifierType(
        uuid=api_json['uuid'],
        display=api_json['display'],
        description=api_json['description'],
    )
