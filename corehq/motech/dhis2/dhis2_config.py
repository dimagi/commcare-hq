from dimagi.ext.couchdbkit import (
    DictProperty,
    DocumentSchema,
    ListProperty,
    SchemaListProperty,
    StringProperty,
)

import corehq.motech.dhis2.serializers  # Required to serialize DHIS2 data types
from corehq.motech.dhis2.const import (
    DHIS2_DATA_TYPE_DATE,
    DHIS2_EVENT_STATUS_COMPLETED,
    DHIS2_EVENT_STATUSES,
    LOCATION_DHIS_ID,
)


class FormDataValueMap(DocumentSchema):
    value = DictProperty()
    data_element_id = StringProperty(required=True)


class Dhis2FormConfig(DocumentSchema):
    xmlns = StringProperty(required=True)
    program_id = StringProperty(required=True)
    org_unit_id = DictProperty(required=False, default={
        "form_user_ancestor_location_field": LOCATION_DHIS_ID
    })
    event_date = DictProperty(required=True, default={
        "form_question": "/metadata/received_on",
        "external_data_type": DHIS2_DATA_TYPE_DATE,
    })
    event_status = StringProperty(
        choices=DHIS2_EVENT_STATUSES,
        default=DHIS2_EVENT_STATUS_COMPLETED,
    )
    completed_date = DictProperty(required=False)
    datavalue_maps = SchemaListProperty(FormDataValueMap)

    @classmethod
    def wrap(cls, data):
        if isinstance(data.get('org_unit_id'), str):
            # Convert org_unit_id from a string to a ConstantValue
            data['org_unit_id'] = {'value': data['org_unit_id']}
        return super(Dhis2FormConfig, cls).wrap(data)


class Dhis2Config(DocumentSchema):
    form_configs = ListProperty(Dhis2FormConfig)
