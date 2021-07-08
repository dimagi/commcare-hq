from typing import List

from corehq.motech.const import COMMCARE_DATA_TYPE_TEXT
from corehq.motech.fhir.const import FHIR_DATA_TYPE_LIST_OF_STRING

from corehq.motech.serializers import serializers


def join_strings(value: List[str]) -> str:
    try:
        return ' '.join(value)
    except TypeError:
        pass


def split_string(value: str) -> List[str]:
    try:
        return value.split(' ')
    except AttributeError:
        pass


serializers.update({
    # (from_data_type, to_data_type): function
    (FHIR_DATA_TYPE_LIST_OF_STRING, COMMCARE_DATA_TYPE_TEXT): join_strings,
    (COMMCARE_DATA_TYPE_TEXT, FHIR_DATA_TYPE_LIST_OF_STRING): split_string,
})
