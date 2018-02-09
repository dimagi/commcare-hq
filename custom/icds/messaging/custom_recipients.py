from __future__ import absolute_import
from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseIndexSQL
from custom.icds.case_relationships import (
    mother_person_case_from_child_health_case,
)
from custom.icds.const import SUPERVISOR_LOCATION_TYPE_CODE
from custom.icds.exceptions import CaseRelationshipError


def recipient_mother_person_case_from_child_health_case(case_schedule_instance):
    try:
        return mother_person_case_from_child_health_case(case_schedule_instance.case)
    except CaseRelationshipError:
        return None


def supervisor_from_awc_owner(case_schedule_instance):
    if not case_schedule_instance.case:
        return None

    # Use one query to lookup the AWC, ensure there is a parent location,
    # and ensure the parent location is a supervisor
    awc = SQLLocation.objects.filter(
        location_id=case_schedule_instance.case.owner_id,
        parent__location_type__code=SUPERVISOR_LOCATION_TYPE_CODE
    ).select_related('parent').first()

    if not awc:
        return None

    return awc.parent
