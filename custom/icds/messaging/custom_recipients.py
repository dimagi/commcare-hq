from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.models import CommCareCaseIndexSQL
from custom.icds.case_relationships import (
    mother_person_case_from_ccs_record_case,
    mother_person_case_from_child_health_case,
    mother_person_case_from_child_person_case,
)
from custom.icds.const import SUPERVISOR_LOCATION_TYPE_CODE
from custom.icds.exceptions import CaseRelationshipError
from datetime import datetime
from dimagi.utils.logging import notify_exception


def skip_notifying_missing_mother_person_case(e):
    # https://manage.dimagi.com/default.asp?271995
    # It's expected that some child person cases will not have a mother person case,
    # so we don't notify when that's the lookup that fails.

    return (
        e.child_case_type == 'person' and
        e.identifier == 'mother' and
        e.relationship == CommCareCaseIndexSQL.CHILD and
        e.num_related_found == 0
    )


def skip_notifying_missing_ccs_record_parent(e):
    # https://manage.dimagi.com/default.asp?277600
    # This is an open issue so it probably doesn't make sense to keep notifying
    # these unless it gets resolved. Going to make these start notifying at a
    # later date so this can be revisited.

    return (
        datetime.utcnow() < datetime(2018, 8, 1) and
        e.child_case_type == 'ccs_record' and
        e.identifier == 'parent' and
        e.relationship == CommCareCaseIndexSQL.CHILD and
        e.num_related_found == 0
    )


def recipient_mother_person_case_from_ccs_record_case(case_schedule_instance):
    try:
        return mother_person_case_from_ccs_record_case(case_schedule_instance.case)
    except CaseRelationshipError as e:
        if not skip_notifying_missing_ccs_record_parent(e):
            notify_exception(None, message="ICDS ccs_record relationship error")

        return None


def recipient_mother_person_case_from_ccs_record_case_excl_migrated_or_opted_out(case_schedule_instance):
    from custom.icds.messaging.custom_content import person_case_is_migrated_or_opted_out

    mother = recipient_mother_person_case_from_ccs_record_case(case_schedule_instance)

    if mother is None or person_case_is_migrated_or_opted_out(mother):
        return None

    return mother


def recipient_mother_person_case_from_child_health_case(case_schedule_instance):
    try:
        return mother_person_case_from_child_health_case(case_schedule_instance.case)
    except CaseRelationshipError as e:
        if not skip_notifying_missing_mother_person_case(e):
            notify_exception(None, message="ICDS child health case relationship error")

        return None


def recipient_mother_person_case_from_child_person_case(case_schedule_instance):
    try:
        return mother_person_case_from_child_person_case(case_schedule_instance.case)
    except CaseRelationshipError as e:
        if not skip_notifying_missing_mother_person_case(e):
            notify_exception(None, message="ICDS child person case relationship error")

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
