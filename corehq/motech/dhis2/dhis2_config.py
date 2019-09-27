from dimagi.ext.couchdbkit import (
    DecimalProperty,
    DocumentSchema,
    ListProperty,
    SchemaDictProperty,
    SchemaListProperty,
    SchemaProperty,
    StringProperty,
)

import corehq.motech.dhis2.serializers  # Required to serialize DHIS2 data types
from corehq.motech.dhis2.const import (
    DHIS2_DATA_TYPE_DATE,
    DHIS2_EVENT_STATUS_COMPLETED,
    DHIS2_EVENT_STATUSES,
    LOCATION_DHIS_ID,
)
from corehq.motech.finders import PropertyWeight
from corehq.motech.value_source import (
    FormQuestion,
    FormUserAncestorLocationField,
    ValueSource,
)


class FormDataValueMap(DocumentSchema):
    value = SchemaProperty(ValueSource)
    data_element_id = StringProperty(required=True)


class Dhis2FormConfig(DocumentSchema):
    xmlns = StringProperty(required=True)
    program_id = StringProperty(required=True)
    org_unit_id = SchemaProperty(ValueSource, required=False, default=FormUserAncestorLocationField(
        location_field=LOCATION_DHIS_ID
    ))
    event_date = SchemaProperty(ValueSource, required=True, default=FormQuestion(
        form_question="/metadata/received_on",
        external_data_type=DHIS2_DATA_TYPE_DATE,
    ))
    event_status = StringProperty(
        choices=DHIS2_EVENT_STATUSES,
        default=DHIS2_EVENT_STATUS_COMPLETED,
    )
    completed_date = SchemaProperty(ValueSource, required=False)
    datavalue_maps = SchemaListProperty(FormDataValueMap)

    @classmethod
    def wrap(cls, data):
        if isinstance(data.get('org_unit_id'), str):
            # Convert org_unit_id from a string to a ConstantString
            data['org_unit_id'] = {
                'doc_type': 'ConstantString',
                'value': data['org_unit_id']
            }
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
    tei_id = SchemaProperty(ValueSource)

    # The corresponding Org Unit of the case's location
    org_unit_id = SchemaProperty(ValueSource)

    # Attribute Type ID to case property / constant
    attributes = SchemaDictProperty(ValueSource)

    # Events for this Tracked Entity:
    form_configs = ListProperty(Dhis2FormConfig)

    finder_config = SchemaProperty(FinderConfig)


class Dhis2EntityConfig(DocumentSchema):
    case_configs = ListProperty(Dhis2CaseConfig)
