from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseIndexSQL


def get_child_health_host_case(domain, extension_case_id):
    child_health_case = CaseAccessors(domain).get_case(extension_case_id)
    if child_health_case.type != 'child_health':
        return None

    related = child_health_case.get_parent(identifier='parent', relationship=CommCareCaseIndexSQL.EXTENSION)
    if not related:
        return None

    return related[0]


def mother_person_case_from_child_health_case(case_schedule_instance):
    person_child_case = get_child_health_host_case(case_schedule_instance.domain, case_schedule_instance.case_id)
    if not person_child_case:
        return None

    related = person_child_case.get_parent(identifier='mother', relationship=CommCareCaseIndexSQL.CHILD)
    if not related:
        return None

    return related[0]
