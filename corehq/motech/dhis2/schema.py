"""
Schema based on DHIS2 `Tracker Web API`_ documentation.


.. _Tracker Web API: https://docs.dhis2.org/master/en/developer/html/webapi_tracker_api.html

"""
from schema import And, Schema

# 1.70.1.8 Tracked entity instance query
# To query for tracked entity instances you can interact with the /api/trackedEntityInstances resource.
tei_query_param_schema = Schema({
    "filter": And(
        "EQ",  # Equal to
        "GT",  # Greater than
        "GE",  # Greater than or equal to
        "LT",  # Less than
        "LE",  # Less than or equal to
        "NE",  # Not equal to
        "LIKE",  # Like (free text match)
        "IN",  # Equal to one of multiple values separated by “;”
    ),  # Attributes to use as a filter for the query. Param can be repeated any number of times. Filters can be applied to a dimension on the format <attribute-id>:<operator>:<filter>[:<operator>:<filter>]. Filter values are case-insensitive and can be repeated together with operator any number of times. Operators can be EQ | GT | GE | LT | LE | NE | LIKE | IN.
    "ou": And(),  # Organisation unit identifiers, separated by “;”.
    "ouMode": And(
        "SELECTED",  # Organisation units defined in the request.
        "CHILDREN",  # The selected organisation units and the immediate children, i.e. the organisation units at the level below.
        "DESCENDANTS",  # The selected organisation units and and all children, i.e. all organisation units in the sub-hierarchy.
        "ACCESSIBLE",  # The data view organisation units associated with the current user and all children, i.e. all organisation units in the sub-hierarchy. Will fall back to data capture organisation units associated with the current user if the former is not defined.
        "CAPTURE",  # The data capture organisation units associated with the current user and all children, i.e. all organisation units in the sub-hierarchy.
        "ALL",  # All organisation units in the system. Requires the ALL authority.
    ),  # The mode of selecting organisation units, can be SELECTED | CHILDREN | DESCENDANTS | ACCESSIBLE | CAPTURE | ALL. Default is SELECTED, which refers to the selected selected organisation units only. See table below for explanations.
    "program": And(),  # Program identifier. Restricts instances to being enrolled in the given program.
    "programStatus": And(),  # Status of the instance for the given program. Can be ACTIVE | COMPLETED | CANCELLED.
    "followUp": And(),  # Follow up status of the instance for the given program. Can be true | false or omitted.
    "programStartDate": And(),  # Start date of enrollment in the given program for the tracked entity instance.
    "programEndDate": And(),  # End date of enrollment in the given program for the tracked entity instance.
    "trackedEntity": And(),  # Tracked entity identifier. Restricts instances to the given tracked instance type.
    "page": And(),  # The page number. Default page is 1.
    "pageSize": And(),  # The page size. Default size is 50 rows per page.
    "totalPages": And(),  # Indicates whether to include the total number of pages in the paging response (implies higher response time).
    "skipPaging": And(),  # Indicates whether paging should be ignored and all rows should be returned.
    "lastUpdatedStartDate": And(),  # Filter for events which were updated after this date. Cannot be used together with lastUpdatedDuration.
    "lastUpdatedEndDate": And(),  # Filter for events which were updated up until this date. Cannot be used together with lastUpdatedDuration.
    "lastUpdatedDuration": And(),  # Include only items which are updated within the given duration. The format is , where the supported time units are “d” (days), “h” (hours), “m” (minutes) and “s” (seconds). Cannot be used together with lastUpdatedStartDate and/or lastUpdatedEndDate.
    "assignedUserMode": And(),  # Restricts result to tei with events assigned based on the assigned user selection mode, can be CURRENT | PROVIDED | NONE | ANY.
    "assignedUser": And(),  # Filter the result down to a limited set of teis with events that are assigned to the given user IDs by using assignedUser=id1;id2.This parameter will be considered only if assignedUserMode is either PROVIDED or null. The API will error out, if for example, assignedUserMode=CURRENT and assignedUser=someId
})

# 1.70.3 Events
event_schema = Schema({
    "program": And(),  # string 	true 		Identifier of the single event with no registration program
    "orgUnit": And(),  # string 	true 		Identifier of the organisation unit where the event took place
    "eventDate": And(),  # date 	true 		The date of when the event occurred
    "completedDate": And(),  # date 	false 		The date of when the event is completed. If not provided, the current date is selected as the event completed date
    "status": And(),  # enum 	false 	ACTIVE | COMPLETED | VISITED | SCHEDULE | OVERDUE | SKIPPED 	Whether the event is complete or not
    "storedBy": And(),  # string 	false 	Defaults to current user 	Who stored this event (can be username, system-name etc)
    "coordinate": And(),  # double 	false 		Refers to where the event took place geographically (latitude and longitude)
    "dataElement": And(),  # string 	true 		Identifier of data element
    "value": And(),  # string 	true 		Data value or measure for this event
})

# Other:
tei_schema = Schema({})  # TODO: ...

# 1.70.4 Relationships
# Relationships are links between two entities in tracker. These entities can be tracked entity instances, enrollments and events.
