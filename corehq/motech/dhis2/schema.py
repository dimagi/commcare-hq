from schema import Optional as SchemaOptional
from schema import Regex, Schema  # noqa: F401

from corehq.motech.dhis2.const import (
    DHIS2_EVENT_STATUSES,
    DHIS2_PROGRAM_STATUSES,
)

id_schema = Regex(r"^[A-Za-z0-9]+$")
# DHIS2 accepts date values, but returns datetime values for dates:
date_schema = Regex(r"^\d{4}-\d{2}-\d{2}(:?T\d{2}:\d{2}:\d{2}.\d{3})?$")
datetime_schema = Regex(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}.\d{3}$")
enrollment_status_schema = Regex(f"^({'|'.join(DHIS2_PROGRAM_STATUSES)})$")
event_status_schema = Regex(f"^({'|'.join(DHIS2_EVENT_STATUSES)})$")


def get_attribute_schema() -> dict:
    return {
        "attribute": id_schema,
        SchemaOptional("code"): str,
        SchemaOptional("created"): datetime_schema,
        SchemaOptional("displayName"): str,
        SchemaOptional("lastUpdated"): datetime_schema,
        SchemaOptional("storedBy"): str,
        "value": object,
        SchemaOptional("valueType"): str,
    }


def get_event_schema() -> dict:
    """
    Returns the schema for a DHIS2 Event.

    >>> event = {
    ...   "program": "eBAyeGv0exc",
    ...   "orgUnit": "DiszpKrYNg8",
    ...   "eventDate": "2013-05-17",
    ...   "status": "COMPLETED",
    ...   "completedDate": "2013-05-18",
    ...   "storedBy": "admin",
    ...   "coordinate": {
    ...     "latitude": 59.8,
    ...     "longitude": 10.9
    ...   },
    ...   "dataValues": [
    ...     { "dataElement": "qrur9Dvnyt5", "value": "22" },
    ...     { "dataElement": "oZg33kd9taw", "value": "Male" },
    ...     { "dataElement": "msodh3rEMJa", "value": "2013-05-18" }
    ...   ]
    ... }
    >>> Schema(get_event_schema()).is_valid(event)
    True

    """
    coordinate_schema = get_coordinate_schema()
    note_schema = get_note_schema()
    relationship_schema = get_relationship_schema()
    user_info_schema = get_user_info_schema()
    return {
        SchemaOptional("assignedUser"): id_schema,
        SchemaOptional("attributeCategoryOptions"): id_schema,
        SchemaOptional("attributeOptionCombo"): id_schema,
        SchemaOptional("completedBy"): str,
        SchemaOptional("completedDate"): date_schema,
        SchemaOptional("coordinate"): coordinate_schema,
        SchemaOptional("created"): datetime_schema,
        SchemaOptional("createdAtClient"): datetime_schema,
        SchemaOptional("createdByUserInfo"): user_info_schema,
        "dataValues": [{
            SchemaOptional("created"): datetime_schema,
            "dataElement": id_schema,
            SchemaOptional("lastUpdated"): datetime_schema,
            SchemaOptional("providedElsewhere"): bool,
            SchemaOptional("storedBy"): str,
            "value": object,
            SchemaOptional("lastUpdatedByUserInfo"): user_info_schema,
            SchemaOptional("createdByUserInfo"): user_info_schema,
        }],
        SchemaOptional("deleted"): bool,
        SchemaOptional("dueDate"): date_schema,
        SchemaOptional("enrollment"): id_schema,
        SchemaOptional("enrollmentStatus"): enrollment_status_schema,
        SchemaOptional("event"): id_schema,
        "eventDate": date_schema,
        SchemaOptional("geometry"): {
            "type": str,
            "coordinates": [float],
        },
        SchemaOptional("lastUpdated"): datetime_schema,
        SchemaOptional("lastUpdatedAtClient"): datetime_schema,
        SchemaOptional("lastUpdatedByUserInfo"): user_info_schema,
        SchemaOptional("notes"): [note_schema],
        "orgUnit": id_schema,
        SchemaOptional("orgUnitName"): str,
        "program": id_schema,
        SchemaOptional("programStage"): id_schema,
        SchemaOptional("relationships"): [relationship_schema],
        SchemaOptional("status"): event_status_schema,
        SchemaOptional("storedBy"): str,
        SchemaOptional("trackedEntityInstance"): id_schema,
    }


def get_note_schema() -> dict:
    return {
        SchemaOptional("note"): id_schema,
        SchemaOptional("storedDate"): date_schema,
        SchemaOptional("storedBy"): str,
        "value": str,
    }


def get_relationship_schema() -> dict:
    return {
        "relationshipType": id_schema,
        SchemaOptional("relationshipName"): str,
        SchemaOptional("relationship"): id_schema,
        SchemaOptional("bidirectional"): bool,
        "from": {
            "trackedEntityInstance": get_tracked_entity_instance_schema()
        },
        "to": {
            "trackedEntityInstance": get_tracked_entity_instance_schema()
        },
        SchemaOptional("created"): datetime_schema,
        SchemaOptional("lastUpdated"): datetime_schema,
    }


def get_tracked_entity_schema() -> dict:
    """
    Returns the schema of a tracked entity instance.
    """
    attribute_schema = get_attribute_schema()
    coordinate_schema = get_coordinate_schema()
    event_schema = get_event_schema()
    geometry_schema = get_geometry_schema()
    note_schema = get_note_schema()
    relationship_schema = get_relationship_schema()
    program_owner_schema = get_program_owner_schema()
    user_info_schema = get_user_info_schema()
    return {
        SchemaOptional("attributes"): [attribute_schema],
        SchemaOptional("created"): datetime_schema,
        SchemaOptional("createdAtClient"): datetime_schema,
        SchemaOptional("deleted"): bool,
        SchemaOptional("enrollments"): [{
            SchemaOptional("attributes"): [attribute_schema],
            SchemaOptional("created"): datetime_schema,
            SchemaOptional("createdAtClient"): datetime_schema,
            SchemaOptional("completedBy"): str,
            SchemaOptional("completedDate"): date_schema,
            SchemaOptional("coordinate"): coordinate_schema,
            SchemaOptional("deleted"): bool,
            SchemaOptional("enrollment"): id_schema,
            SchemaOptional("enrollmentDate"): date_schema,
            SchemaOptional("events"): [event_schema],
            SchemaOptional("geometry"): geometry_schema,
            SchemaOptional("incidentDate"): date_schema,
            SchemaOptional("lastUpdated"): datetime_schema,
            SchemaOptional("lastUpdatedAtClient"): datetime_schema,
            SchemaOptional("notes"): [note_schema],
            "orgUnit": id_schema,
            SchemaOptional("orgUnitName"): str,
            "program": id_schema,
            SchemaOptional("relationships"): [relationship_schema],
            SchemaOptional("status"): enrollment_status_schema,
            SchemaOptional("storedBy"): str,
            SchemaOptional("trackedEntityInstance"): id_schema,
            SchemaOptional("trackedEntityType"): id_schema,
            SchemaOptional("lastUpdatedByUserInfo"): user_info_schema,
            SchemaOptional("createdByUserInfo"): user_info_schema
        }],
        SchemaOptional("featureType"): str,
        SchemaOptional("geometry"): geometry_schema,
        SchemaOptional("inactive"): bool,
        SchemaOptional("lastUpdated"): datetime_schema,
        SchemaOptional("lastUpdatedAtClient"): datetime_schema,
        "orgUnit": id_schema,
        SchemaOptional("potentialDuplicate"): bool,
        SchemaOptional("programOwners"): [program_owner_schema],
        SchemaOptional("relationships"): [relationship_schema],
        SchemaOptional("storedBy"): str,
        SchemaOptional("trackedEntityInstance"): id_schema,
        "trackedEntityType": id_schema,
        SchemaOptional("lastUpdatedByUserInfo"): user_info_schema,
        SchemaOptional("createdByUserInfo"): user_info_schema
    }


def get_coordinate_schema():
    return {
        "latitude": float,
        "longitude": float,
    }


def get_geometry_schema():
    return {
        "type": str,
        "coordinates": [float],
    }


def get_user_info_schema():
    return {
        "firstName": str,
        "surname": str,
        "uid": id_schema,
        "username": str,
    }


def get_program_owner_schema():
    return {
        "ownerOrgUnit": id_schema,
        "program": id_schema,
        "trackedEntityInstance": id_schema,
    }


def get_tracked_entity_instance_schema():
    return {
        "trackedEntityInstance": id_schema,
        SchemaOptional("programOwners"): [get_program_owner_schema()],
        SchemaOptional("potentialDuplicate"): bool,
    }
