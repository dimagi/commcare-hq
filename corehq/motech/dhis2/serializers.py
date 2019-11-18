from corehq.motech.dhis2.const import (
    DHIS2_DATA_TYPE_DATE,
    DHIS2_DATA_TYPE_INTEGER,
    DHIS2_DATA_TYPE_NUMBER,
    DHIS2_DATA_TYPE_TEXT,
)
from corehq.motech.serializers import (
    serializers,
    to_date_str,
    to_decimal,
    to_integer,
    to_text,
)

serializers.update({
    # (from_data_type, to_data_type): function
    (None, DHIS2_DATA_TYPE_DATE): to_date_str,
    (None, DHIS2_DATA_TYPE_INTEGER): to_integer,
    (None, DHIS2_DATA_TYPE_NUMBER): to_decimal,
    (None, DHIS2_DATA_TYPE_TEXT): to_text,
})
