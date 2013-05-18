from casexml.apps.case.models import CommCareCase


def any_action_property(action, props):
    for p in props:
        if p in action.updated_unknown_properties and action.updated_unknown_properties[p]:
            return True
    return False


def get_related_props(case, property):
    """
    Gets the specified property for all child cases in which that property exists
    """
    if not hasattr(case, '_subcase_cache'):
        case._subcase_cache = {}

    for index in case.reverse_indices:
        subcase_id = index.referenced_id
        if subcase_id not in case._subcase_cache:
            case._subcase_cache[subcase_id] = CommCareCase.get(subcase_id)
        subcase = case._subcase_cache[subcase_id]
        subcase_property = getattr(subcase, property, None)
        if subcase_property:
            yield subcase_property


def get_related_prop(case, property):
    for value in get_related_props(case, property):
        return value
    return None