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

    for index in case.reverse_indices:
        referenced_case = CommCareCase.get(index.referenced_id)
        if getattr(referenced_case, property, None):
            yield getattr(referenced_case, property)


def get_related_prop(case, property):
    for value in get_related_props(case, property):
        return value
    return None