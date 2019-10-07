from collections import defaultdict

from django.utils.translation import ugettext as _

from requests import HTTPError

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.logging import notify_exception

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.motech.dhis2.const import DHIS2_API_VERSION, XMLNS_DHIS2
from corehq.motech.dhis2.events_helpers import get_event
from corehq.motech.dhis2.exceptions import (
    BadTrackedEntityInstanceID,
    Dhis2Exception,
    MultipleInstancesFound,
)
from corehq.motech.dhis2.finders import TrackedEntityInstanceFinder
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.utils import pformat_json
from corehq.motech.value_source import CaseTriggerInfo


def send_dhis2_entities(requests, dhis2_entity_config, case_trigger_infos):
    """
    Send request to register / update tracked entities
    """
    errors = []
    for info in case_trigger_infos:
        assert isinstance(info, CaseTriggerInfo)
        case_config = get_case_config_for_case_type(info.type, dhis2_entity_config)
        if not case_config:
            # This payload includes a case of a case type that does not correspond to a tracked entity type
            continue

        try:
            tracked_entity, etag = get_tracked_entity_and_etag(requests, info, case_config)
            if tracked_entity:
                update_tracked_entity_instance(requests, tracked_entity, etag, info, case_config)
            else:
                tracked_entity = register_tracked_entity_instance(requests, info, case_config)
                save_tracked_entity_instance_id(requests.domain_name, tracked_entity, info, case_config)
        except (Dhis2Exception, HTTPError) as err:
            errors.append(str(err))
            notify_exception(err)

    if errors:
        return RepeaterResponse(400, 'Bad Request', "Errors: " + pformat_json([str(e) for e in errors]))
    return RepeaterResponse(200, "OK")


def get_case_config_for_case_type(case_type, dhis2_entity_config):
    for case_config in dhis2_entity_config.case_configs:
        if case_config.case_type == case_type:
            return case_config


def get_tracked_entity_and_etag(requests, case_trigger_info, case_config):
    """
    Returns a tracked entity that corresponds to case_trigger_info and
    its ETag, or (None, None) if a corresponding Tracked Entity was not
    found.

    Raises BadTrackedEntityInstanceID if a Tracked Entity ID believed to
    have been issued by the DHIS2 server is not found on that server.

    Raises MultipleInstancesFound if unable to select a
    corresponding Tracked Entity from multiple available candidates.
    """
    tei_id = get_tracked_entity_instance_id(case_trigger_info, case_config)
    if not tei_id:
        tracked_entities = find_tracked_entity_instances(requests, case_trigger_info, case_config)
        if not tracked_entities:
            return (None, None)
        if len(tracked_entities) > 1:
            msg = _(f'Found {len(tracked_entities)} tracked entity instances '
                    f'for {case_trigger_info}')
            raise MultipleInstancesFound(requests.domain_name, requests.base_url, requests.username, msg)
        tei_id = tracked_entities[0]["trackedEntityInstance"]
    return get_tracked_entity_instance_and_etag_by_id(requests, tei_id, case_trigger_info)


def get_tracked_entity_instance_id(case_trigger_info, case_config):
    """
    Return the Tracked Entity instance ID stored in a case property (or
    other value source like a form question or a constant).
    """
    tei_id_value_source = case_config.tei_id
    return tei_id_value_source.get_value(case_trigger_info)


def get_tracked_entity_instance_and_etag_by_id(requests, tei_id, case_trigger_info):
    """
    Fetch a tracked entity instance from a DHIS2 server by its TEI ID,
    and return it with its ETag.

    Raises BadTrackedEntityInstanceID if the ID does not belong to an
    instance.
    """
    endpoint = f"/api/{DHIS2_API_VERSION}/trackedEntityInstances/{tei_id}"
    params = {"fields": "*"}  # Tells DHIS2 to return everything
    response = requests.get(endpoint, params=params)
    if 200 <= response.status_code < 300:
        return response.json(), response.headers["ETag"]
    else:
        msg = _(f'The tracked entity instance ID "{tei_id}" of '
                f'{case_trigger_info} was not found on its DHIS2 server.')
        raise BadTrackedEntityInstanceID(requests.domain_name, requests.base_url, requests.username, msg)


def find_tracked_entity_instances(requests, case_trigger_info, case_config):
    finder = TrackedEntityInstanceFinder(requests, case_config)
    return finder.find_tracked_entity_instances(case_trigger_info)


def update_tracked_entity_instance(requests, tracked_entity, etag, case_trigger_info, case_config):
    for attr_id, value_source in case_config.attributes.items():
        set_te_attr(tracked_entity, attr_id, value_source.get_value(case_trigger_info))
    enrollments = get_enrollments(case_trigger_info, case_config)
    if enrollments:
        tracked_entity["enrollments"] = enrollments
    tei_id = tracked_entity["trackedEntityInstance"]
    endpoint = f"/api/{DHIS2_API_VERSION}/trackedEntityInstances/{tei_id}"
    headers = {
        "Content-type": "application/json",
        "Accept": "application/json"
    }
    if not etag.startswith("W/"):  # weak ETags never match
        headers['If-Match'] = etag
    response = requests.put(endpoint, json=tracked_entity, headers=headers)
    if response.status_code == 412:  # Precondition failed
        tei_id = tracked_entity["trackedEntityInstance"]
        tracked_entity, etag = get_tracked_entity_instance_and_etag_by_id(requests, tei_id, case_trigger_info)
        update_tracked_entity_instance(requests, tracked_entity, etag, case_trigger_info, case_config)
    else:
        response.raise_for_status()


def register_tracked_entity_instance(requests, case_trigger_info, case_config):
    tracked_entity = {
        "trackedEntityType": case_config.te_type_id,
        "orgUnit": case_config.org_unit_id.get_value(case_trigger_info),
        "attributes": [],
    }
    for attr_id, value_source in case_config.attributes.items():
        set_te_attr(tracked_entity, attr_id, value_source.get_value(case_trigger_info))
    enrollments = get_enrollments(case_trigger_info, case_config)
    if enrollments:
        tracked_entity["enrollments"] = enrollments
    endpoint = f"/api/{DHIS2_API_VERSION}/trackedEntityInstances/"
    response = requests.post(endpoint, json=tracked_entity, raise_for_status=True)
    summaries = response.json()["response"]["importSummaries"]
    if len(summaries) != 1:
        raise Dhis2Exception(
            requests.domain_name, requests.base_url, requests.username,
            _(f'{len(summaries)} tracked entity instances registered from {case_trigger_info}.')
        )
    tracked_entity["trackedEntityInstance"] = summaries[0]["reference"]
    return tracked_entity


def get_enrollments(case_trigger_info, case_config):
    events_by_program = get_events_by_program(case_trigger_info, case_config)
    enrollments = []
    for program, events in events_by_program.items():
        enrollment = {
            "program": program,
            "events": events,
        }
        enrollments.append(enrollment)
    return enrollments


def get_events_by_program(case_trigger_info, case_config):
    events_by_program = defaultdict(list)
    for form_config in case_config.form_configs:
        event = get_event(case_trigger_info.domain, form_config, info=case_trigger_info)
        events_by_program[event["program"]].append(event)
    return events_by_program


def save_tracked_entity_instance_id(domain, tracked_entity, case_trigger_info, case_config):
    if case_config["tei_id"] and "case_property" in case_config["tei_id"]:
        tei_id = tracked_entity["trackedEntityInstance"]
        case_property = case_config["tei_id"]["case_property"]
        if case_property == "external_id":
            case_update = {}
            kwargs = {case_property: tei_id}
        else:
            case_update = {case_property: tei_id}
            kwargs = {}
        case_block = CaseBlock(
            case_id=case_trigger_info.case_id,
            create=False,
            update=case_update,
            **kwargs
        )
        submit_case_blocks([case_block.as_text()], domain, xmlns=XMLNS_DHIS2)


def set_te_attr(tracked_entity, attr_id, value):
    for attr in tracked_entity["attributes"]:
        if attr["attribute"] == attr_id:
            attr["value"] = value
            break
    else:
        tracked_entity["attributes"].append(
            {"attribute": attr_id, "value": value}
        )
