from typing import List

from corehq.motech.const import COMMCARE_DATA_TYPE_TEXT
from corehq.motech.fhir.const import FHIR_DATA_TYPE_LIST_OF_STRING

from corehq.motech.serializers import serializers


def join_strings(value: List[str]) -> str:
    return ' '.join(value)


def split_string(value: str) -> List[str]:
    return value.split(' ')


serializers.update({
    # (from_data_type, to_data_type): function
    (FHIR_DATA_TYPE_LIST_OF_STRING, COMMCARE_DATA_TYPE_TEXT): join_strings,
    (COMMCARE_DATA_TYPE_TEXT, FHIR_DATA_TYPE_LIST_OF_STRING): split_string,
})
