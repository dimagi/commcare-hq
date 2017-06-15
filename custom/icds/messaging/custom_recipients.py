from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.models import CommCareCaseIndexSQL


def mother_person_case_from_child_health_case(case_schedule_instance):
    child_health_case = CaseAccessors(case_schedule_instance.domain).get_case(case_schedule_instance.case_id)
    if child_health_case.type != 'child_health':
        return None

    related = child_health_case.get_parent(identifier='parent', relationship=CommCareCaseIndexSQL.EXTENSION)
    if not related:
        return None

    person_child_case = related[0]
    related = person_child_case.get_parent(identifier='mother', relationship=CommCareCaseIndexSQL.CHILD)
    if not related:
        return None

    return related[0]
