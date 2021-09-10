from collections import defaultdict
from typing import Any, Dict, List

from django.urls import reverse
from django.utils.translation import ugettext as _

from requests import HTTPError
from schema import Schema, SchemaError

from casexml.apps.case.mock import CaseBlock

from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.motech.dhis2.const import XMLNS_DHIS2
from corehq.motech.dhis2.events_helpers import get_event, _get_coordinate
from corehq.motech.dhis2.exceptions import (
    BadTrackedEntityInstanceID,
    Dhis2Exception,
    MultipleInstancesFound,
)
from corehq.motech.dhis2.finders import TrackedEntityInstanceFinder
from corehq.motech.dhis2.schema import get_tracked_entity_schema
from corehq.motech.exceptions import ConfigurationError
from corehq.motech.repeater_helpers import RepeaterResponse
from corehq.motech.utils import pformat_json
from corehq.motech.value_source import (
    get_case_trigger_info_for_case,
    get_value,
)


def send_dhis2_entities(requests, repeater, case_trigger_infos):
    """
    Send request to register / update tracked entities
    """
    errors = []
    info_config_pairs = _get_info_config_pairs(repeater, case_trigger_infos)
    for info, case_config in info_config_pairs:
        try:
            tracked_entity, etag = get_tracked_entity_and_etag(requests, info, case_config)
            if tracked_entity:
                update_tracked_entity_instance(requests, tracked_entity, etag, info, case_config)
            else:
                register_tracked_entity_instance(requests, info, case_config)
        except (Dhis2Exception, HTTPError) as err:
            errors.append(str(err))

    # Create relationships after handling tracked entity instances, to
    # ensure that both the instances in the relationship have been created.
    for info, case_config in info_config_pairs:
        if not case_config.relationships_to_export:
            continue
        try:
            create_relationships(
                requests,
                info,
                case_config,
                repeater.dhis2_entity_config,
            )
        except (Dhis2Exception, HTTPError) as err:
            errors.append(str(err))

    if errors:
        errors_str = f"Errors sending to {repeater}: " + pformat_json([str(e) for e in errors])
        requests.notify_error(errors_str)
        return RepeaterResponse(400, 'Bad Request', errors_str)
    return RepeaterResponse(200, "OK")


def _get_info_config_pairs(repeater, case_trigger_infos):
    info_config_pairs = []
    for info in case_trigger_infos:
        case_config = get_case_config_for_case_type(
            info.type,
            repeater.dhis2_entity_config,
        )
        if not case_config:
            # This payload includes a case of a case type that does not
            # correspond to a tracked entity type
            continue
        info_config_pairs.append((info, case_config))
    return info_config_pairs


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
        tracked_entities = find_tracked_entity_instances(
            requests, case_trigger_info, case_config
        )
        if not tracked_entities:
            return (None, None)
        if len(tracked_entities) > 1:
            raise MultipleInstancesFound(_(
                '{n} tracked entity instances were found for case {case}'
            ).format(n=len(tracked_entities), case=case_trigger_info))
        tei_id = tracked_entities[0]["trackedEntityInstance"]
    return get_tracked_entity_instance_and_etag_by_id(
        requests, tei_id, case_trigger_info
    )


def get_tracked_entity_instance_id(case_trigger_info, case_config):
    """
    Return the Tracked Entity instance ID stored in a case property (or
    other value source like a form question or a constant).
    """
    tei_id_value_source = case_config.tei_id
    return get_value(tei_id_value_source, case_trigger_info)


def get_tracked_entity_instance_and_etag_by_id(requests, tei_id, case_trigger_info):
    """
    Fetch a tracked entity instance from a DHIS2 server by its TEI ID,
    and return it with its ETag.

    Raises BadTrackedEntityInstanceID if the ID does not belong to an
    instance.
    """
    endpoint = f"/api/trackedEntityInstances/{tei_id}"
    params = {"fields": "*"}  # Tells DHIS2 to return everything
    response = requests.get(endpoint, params=params)
    if 200 <= response.status_code < 300:
        return response.json(), response.headers["ETag"]
    else:
        raise BadTrackedEntityInstanceID(_(
            'The tracked entity instance ID "{id}" of case {case} was not '
            'found on its DHIS2 server.'
        ).format(id=tei_id, case=case_trigger_info))


def find_tracked_entity_instances(requests, case_trigger_info, case_config):
    finder = TrackedEntityInstanceFinder(requests, case_config)
    return finder.find_tracked_entity_instances(case_trigger_info)


def update_tracked_entity_instance(
    requests, tracked_entity, etag, case_trigger_info, case_config,
    attempt=1
):
    case_updates = {}
    for attr_id, value_source_config in case_config.attributes.items():
        value, case_update = get_or_generate_value(
            requests, attr_id, value_source_config, case_trigger_info
        )
        set_te_attr(tracked_entity["attributes"], attr_id, value)
        case_updates.update(case_update)
    enrollments_with_new_events = get_enrollments(
        case_trigger_info,
        case_config,
    )
    if enrollments_with_new_events:
        tracked_entity["enrollments"] = update_enrollments(
            tracked_entity, enrollments_with_new_events
        )
    validate_tracked_entity(tracked_entity)
    tei_id = tracked_entity["trackedEntityInstance"]
    endpoint = f"/api/trackedEntityInstances/{tei_id}"
    headers = {
        "Content-type": "application/json",
        "Accept": "application/json",
        "If-Match": etag,
    }
    response = requests.put(endpoint, json=tracked_entity, headers=headers)
    if response.status_code == 412 and attempt <= 3:
        # Precondition failed: etag does not match. tracked_entity has
        # been changed since we fetched their details. Try again.
        tracked_entity, etag = get_tracked_entity_instance_and_etag_by_id(
            requests, tei_id, case_trigger_info
        )
        update_tracked_entity_instance(
            requests, tracked_entity, etag, case_trigger_info, case_config,
            attempt=attempt + 1
        )
    else:
        response.raise_for_status()
    if case_updates:
        save_case_updates(requests.domain_name, case_trigger_info.case_id, case_updates)


def update_enrollments(
    tracked_entity: Dict,
    enrollments_with_new_events: List,
) -> List:
    """
    Adds new events to current program enrollments and adds new
    enrollments. Returns a complete list of enrollments.
    """
    current_enrollments = tracked_entity.get("enrollments", [])
    enrollments_by_program_id = {e["program"]: e for e in current_enrollments}
    for enrol in enrollments_with_new_events:
        program_id = enrol["program"]
        if program_id in enrollments_by_program_id:
            enrollments_by_program_id[program_id]["events"].extend(enrol["events"])
            enrollments_by_program_id[program_id]["status"] = enrol["status"]
        else:
            enrollments_by_program_id[program_id] = enrol
    return list(enrollments_by_program_id.values())


def register_tracked_entity_instance(requests, case_trigger_info, case_config):
    case_updates = {}
    tracked_entity = {
        "trackedEntityType": case_config.te_type_id,
        "orgUnit": get_value(case_config.org_unit_id, case_trigger_info),
        "attributes": [],
    }

    for attr_id, value_source_config in case_config.attributes.items():
        value, case_update = get_or_generate_value(
            requests, attr_id, value_source_config, case_trigger_info
        )
        set_te_attr(tracked_entity["attributes"], attr_id, value)
        case_updates.update(case_update)
    enrollments = get_enrollments(case_trigger_info, case_config)
    if enrollments:
        tracked_entity["enrollments"] = enrollments
    validate_tracked_entity(tracked_entity)
    endpoint = "/api/trackedEntityInstances/"
    response = requests.post(endpoint, json=tracked_entity, raise_for_status=True)
    summaries = response.json()["response"]["importSummaries"]
    if len(summaries) != 1:
        raise Dhis2Exception(_(
            '{n} tracked entity instances were registered from case {case}.'
        ).format(n=len(summaries), case=case_trigger_info))
    if case_config["tei_id"] and "case_property" in case_config["tei_id"]:
        case_property = case_config["tei_id"]["case_property"]
        tei_id = summaries[0]["reference"]
        case_updates[case_property] = tei_id
        # Store `tei_id` in `case_trigger_info` because we might need it
        # when we create relationships.
        case_trigger_info.extra_fields[case_property] = tei_id
    if case_updates:
        save_case_updates(requests.domain_name, case_trigger_info.case_id, case_updates)


def create_relationships(
    requests,
    subcase_trigger_info,
    subcase_config,
    dhis2_entity_config,
):
    """
    Creates two relationships in DHIS2; one corresponding to a
    subcase-to-supercase relationship, and the other corresponding to a
    supercase-to-subcase relationship.
    """
    subcase_tei_id = get_value(subcase_config.tei_id, subcase_trigger_info)
    if not subcase_tei_id:
        raise Dhis2Exception(_(
            'Unable to create DHIS2 relationship: The case {case} is not '
            'registered in DHIS2.'
        ).format(case=subcase_trigger_info))

    for rel_config in subcase_config.relationships_to_export:
        supercase = get_supercase(subcase_trigger_info, rel_config)
        supercase_config = get_case_config_for_case_type(
            supercase.type,
            dhis2_entity_config,
        )
        supercase_info = get_case_trigger_info_for_case(
            supercase,
            [supercase_config.tei_id],
        )
        supercase_tei_id = get_value(supercase_config.tei_id, supercase_info)
        if not supercase_tei_id:
            # The problem could be that the relationship is configured
            # in the CaseConfig for the subcase's case type, but there
            # is no CaseConfig for the supercase's case type.
            # Alternatively, registering the supercase in DHIS2 failed.
            raise ConfigurationError(_(
                'Unable to create DHIS2 relationship: The case {case} is not '
                'registered in DHIS2.'
            ).format(case=supercase_info))
        if rel_config.supercase_to_subcase_dhis2_id:
            create_relationship(
                requests,
                rel_config.supercase_to_subcase_dhis2_id,
                supercase_tei_id,
                subcase_tei_id,
            )
        if rel_config.subcase_to_supercase_dhis2_id:
            create_relationship(
                requests,
                rel_config.subcase_to_supercase_dhis2_id,
                subcase_tei_id,
                supercase_tei_id,
            )


def get_supercase(case_trigger_info, relationship_config):
    case_accessor = CaseAccessors(case_trigger_info.domain)
    case = case_accessor.get_case(case_trigger_info.case_id)
    for index in case.live_indices:
        index_matches_config = (
            index.identifier == relationship_config.identifier
            and index.referenced_type == relationship_config.referenced_type
            and index.relationship == relationship_config.relationship
        )
        if index_matches_config:
            return case_accessor.get_case(index.referenced_id)


def create_relationship(requests, rel_type_id, from_tei_id, to_tei_id):
    relationship = {
        'relationshipType': rel_type_id,
        'from': {
            'trackedEntityInstance': {
                'trackedEntityInstance': from_tei_id
            }
        },
        'to': {
            'trackedEntityInstance': {
                'trackedEntityInstance': to_tei_id
            }
        }
    }
    endpoint = '/api/relationships/'
    response = requests.post(endpoint, json=relationship, raise_for_status=True)
    num_imported = response.json()['response']['imported']
    if num_imported != 1:
        from corehq.motech.views import MotechLogListView
        raise Dhis2Exception(_(
            'DHIS2 created {n} relationships. Errors from DHIS2 can be found '
            'in Remote API Logs: {url}'
        ).format(n=num_imported, url=reverse(MotechLogListView.urlname)))


def get_or_generate_value(requests, attr_id, value_source_config, case_trigger_info):
    """
    Returns the value of ``value_source_config``, or a generated value
    returned by DHIS2, and a case update if the generated value should
    be saved in a case property.
    """
    case_update = {}

    # Instead of adding DHIS2-specific properties to the ValueSource
    # class, pop them here first.
    # Is the attribute generated by DHIS2 (e.g. unique IDs)?
    is_generated = value_source_config.pop("is_generated", False)
    # A dictionary of GET param name: value_source pairs
    generator_params = value_source_config.pop("generator_params", {})

    value = get_value(value_source_config, case_trigger_info)
    if is_blank(value) and is_generated:
        value = generate_value(requests, attr_id, generator_params, case_trigger_info)
        if "case_property" in value_source_config:
            case_update[value_source_config["case_property"]] = value
    return value, case_update


def is_blank(value):
    return value is None or value == ""


def generate_value(requests, attr_id, generator_params, case_trigger_info):
    """
    Sends a request to DHIS2 to generate a value for a generated
    attribute, like a unique ID. DHIS2 may require parameters to
    generate the value. Returns the value.

    Example value source::

        {
            "case_property": "dhis2_unique_id",
            "is_generated": True,
            "generator_params": {
                "ORG_UNIT_CODE": {
                    "case_owner_ancestor_location_field": "dhis2_org_unit_code"
                }
            }
        }

    """
    params = {name: get_value(vsc, case_trigger_info) for name, vsc in generator_params.items()}
    response = requests.get(
        f"/api/trackedEntityAttributes/{attr_id}/generate",
        params=params, raise_for_status=True
    )
    return response.json()["value"]


def get_enrollments(case_trigger_info, case_config):
    """
    DHIS2 allows tracked entity instances to be enrolled in programs
    without any events, but CommCare does not currently have a mechanism
    for that. Cases/TEIs are enrolled in a program when the first event
    in that program occurs.
    """
    case_org_unit = get_value(case_config.org_unit_id, case_trigger_info)
    programs_by_id = get_programs_by_id(case_trigger_info, case_config)
    enrollments = []
    for program_id, program in programs_by_id.items():
        enrollment = {
            "orgUnit": program["orgUnit"] or case_org_unit,
            "program": program_id,
            "status": program["status"],
            "events": program["events"],
        }
        if program.get("geometry"):
            enrollment["geometry"] = program["geometry"]
        if program.get("enrollmentDate"):
            enrollment["enrollmentDate"] = program["enrollmentDate"]
        if program.get("incidentDate"):
            enrollment["incidentDate"] = program["incidentDate"]
        enrollments.append(enrollment)
    return enrollments


def get_programs_by_id(case_trigger_info, case_config):
    programs_by_id = defaultdict(lambda: {"events": []})
    for form_config in case_config.form_configs:
        if case_trigger_info.form_question_values['/metadata/xmlns'] != form_config.xmlns:
            continue
        event = get_event(case_trigger_info.domain, form_config, info=case_trigger_info)
        if event:
            program = programs_by_id[event["program"]]
            program["events"].append(event)
            program["orgUnit"] = get_value(form_config.org_unit_id, case_trigger_info)
            program["status"] = get_value(form_config.program_status, case_trigger_info)
            program["geometry"] = get_geo_json(form_config, case_trigger_info)
            program.update(get_program_dates(form_config, case_trigger_info))
    return programs_by_id


def get_program_dates(form_config, case_trigger_info):
    program = {}
    if form_config.enrollment_date:
        enrollment_date = get_value(form_config.enrollment_date, case_trigger_info)
        if enrollment_date:
            program["enrollmentDate"] = enrollment_date
    if form_config.incident_date:
        incident_date = get_value(form_config.incident_date, case_trigger_info)
        if incident_date:
            program["incidentDate"] = incident_date
    return program


def save_case_updates(domain, case_id, case_updates):
    case_update = {}
    kwargs = {}
    for case_property, value in case_updates.items():
        if case_property == "external_id":
            kwargs[case_property] = value
        else:
            case_update[case_property] = value
    case_block = CaseBlock.deprecated_init(
        case_id=case_id,
        create=False,
        update=case_update,
        **kwargs
    )
    submit_case_blocks([case_block.as_text()], domain, xmlns=XMLNS_DHIS2)


def set_te_attr(
    attributes: List[Dict[str, Any]],
    attr_id: str,
    value: Any
):
    """
    Updates a list of tracked entity attributes by reference

    >>> attrs = [{"attribute": "abc123", "value": "ham"}]
    >>> set_te_attr(attrs, "abc123", "spam")
    >>> set_te_attr(attrs, "def456", "spam")
    >>> attrs
    [{'attribute': 'abc123', 'value': 'spam'}, {'attribute': 'def456', 'value': 'spam'}]

    """
    for attr in attributes:
        if attr["attribute"] == attr_id:
            attr["value"] = value
            break
    else:
        attributes.append(
            {"attribute": attr_id, "value": value}
        )


def validate_tracked_entity(tracked_entity):
    """
    Raises ConfigurationError if ``tracked_entity`` does not match its
    schema.
    """
    try:
        Schema(get_tracked_entity_schema()).validate(tracked_entity)
    except SchemaError as err:
        raise ConfigurationError from err


def get_tracked_entity_type(requests, entity_type_id):
    endpoint = f"/api/trackedEntityTypes/{entity_type_id}"
    response = requests.get(endpoint, raise_for_status=True)
    return response.json()


def get_geo_json(form_config, case_trigger_info):
    coordinate_dict = _get_coordinate(form_config, case_trigger_info)
    if coordinate_dict.get('coordinate'):
        point = coordinate_dict['coordinate']
        return {
            'type': 'Point',
            'coordinates': [
                point['latitude'],
                point['longitude']
            ]
        }
    return {}
