from dimagi.ext.couchdbkit import (
    DecimalProperty,
    DictProperty,
    DocumentSchema,
    ListProperty,
    SchemaListProperty,
    SchemaProperty,
    StringProperty,
)

import corehq.motech.dhis2.serializers  # Required to serialize DHIS2 data types
from corehq.motech.dhis2.const import (
    DHIS2_DATA_TYPE_DATE,
    DHIS2_EVENT_STATUS_COMPLETED,
    DHIS2_EVENT_STATUSES,
    DHIS2_PROGRAM_STATUS_ACTIVE,
    DHIS2_PROGRAM_STATUSES,
    LOCATION_DHIS_ID,
)
from corehq.motech.finders import PropertyWeight


class FormDataValueMap(DocumentSchema):
    value = DictProperty()
    data_element_id = StringProperty(required=True)


class Dhis2FormConfig(DocumentSchema):
    xmlns = StringProperty(required=True)
    program_id = StringProperty(required=True)
    enrollment_date = DictProperty(required=False)
    incident_date = DictProperty(required=False)
    program_stage_id = DictProperty(required=False)
    program_status = DictProperty(required=False, default={
        "value": DHIS2_PROGRAM_STATUS_ACTIVE
    })
    org_unit_id = DictProperty(required=False, default={
        "form_user_ancestor_location_field": LOCATION_DHIS_ID
    })
    event_date = DictProperty(required=True, default={
        "form_question": "/metadata/received_on",
        "external_data_type": DHIS2_DATA_TYPE_DATE,
    })
    event_status = DictProperty(required=False, default={
        "value": DHIS2_EVENT_STATUS_COMPLETED
    })
    completed_date = DictProperty(required=False)
    datavalue_maps = SchemaListProperty(FormDataValueMap)
    event_location = DictProperty(required=False, default={})

    @classmethod
    def wrap(cls, data):
        if isinstance(data.get('org_unit_id'), str):
            # Convert org_unit_id from a string to a ConstantValue
            data['org_unit_id'] = {'value': data['org_unit_id']}
        if isinstance(data.get('event_status'), str):
            data['event_status'] = {'value': data['event_status']}
        if isinstance(data.get('program_status'), str):
            data['program_status'] = {'value': data['program_status']}
        return super(Dhis2FormConfig, cls).wrap(data)


class Dhis2Config(DocumentSchema):
    form_configs = ListProperty(Dhis2FormConfig)


class FinderConfig(DocumentSchema):
    property_weights = ListProperty(PropertyWeight)
    confidence_margin = DecimalProperty(default=0.5)


class Dhis2CaseConfig(DocumentSchema):
    """
    A Dhis2CaseConfig maps a case type to a tracked entity type.
    """
    case_type = StringProperty()

    # The ID of the Tracked Entity type. e.g. the ID of "Person"
    te_type_id = StringProperty()

    # The case property to store the ID of the corresponding Tracked
    # Entity instance. If this is not set, MOTECH will search for a
    # matching Tracked Entity on every payload.
    tei_id = DictProperty()

    # The corresponding Org Unit of the case's location
    org_unit_id = DictProperty()

    # Attribute Type ID to case property / constant
    attributes = DictProperty()

    # Events for this Tracked Entity:
    form_configs = ListProperty(Dhis2FormConfig)

    finder_config = SchemaProperty(FinderConfig)


class Dhis2EntityConfig(DocumentSchema):
    case_configs = ListProperty(Dhis2CaseConfig)
