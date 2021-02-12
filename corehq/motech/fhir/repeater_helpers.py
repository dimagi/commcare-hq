from typing import List, Optional

from corehq.motech.requests import Requests
from corehq.motech.value_source import CaseTriggerInfo


def register_patients(
    requests: Requests,
    case_trigger_infos: List[CaseTriggerInfo],
    fhir_version: str,
):
    raise NotImplementedError


def get_fhir_bundle(
    case_trigger_infos: List[CaseTriggerInfo],
    fhir_version: str,
) -> Optional[dict]:
    raise NotImplementedError


def send_bundle(
    requests: Requests,
    bundle: dict,
):
    raise NotImplementedError
