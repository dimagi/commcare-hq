from corehq.apps.locations.models import SQLLocation
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseIndexSQL
from custom.icds.const import SUPERVISOR_LOCATION_TYPE_CODE


def get_child_health_host_case(domain, extension_case_id):
    child_health_case = CaseAccessors(domain).get_case(extension_case_id)
    if child_health_case.type != 'child_health':
        return None

    related = child_health_case.get_parent(identifier='parent', relationship=CommCareCaseIndexSQL.EXTENSION)
    if not related:
        return None

    return related[0]


def mother_person_case_from_ccs_record_case(case_schedule_instance):
    if case_schedule_instance.case.type != 'ccs_record':
        return None

    related = case_schedule_instance.case.get_parent(identifier='parent', relationship=CommCareCaseIndexSQL.CHILD)
    if not related:
        return None

    mother_case = related[0]
    if mother_case.type != 'person':
        return None

    return mother_case


def mother_person_case_from_child_health_case(case_schedule_instance):
    person_child_case = get_child_health_host_case(case_schedule_instance.domain, case_schedule_instance.case_id)
    if not person_child_case:
        return None

    related = person_child_case.get_parent(identifier='mother', relationship=CommCareCaseIndexSQL.CHILD)
    if not related:
        return None

    return related[0]


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
