from casexml.apps.case.models import CommCareCase


def any_action_property(action, props):
    for p in props:
        if p in action.updated_unknown_properties and action.updated_unknown_properties[p]:
            return True
    return False


def get_related_prop(case, property, latest=True):
    """
    Gets the specified property for latest referenced case in which that property exists
    """
    actions = case.actions[::-1] if latest else case.actions
    for action in actions:
        for index in action.indices:
            referenced_case = CommCareCase.get(index.referenced_id)
            if getattr(referenced_case, property, None):
                return getattr(referenced_case, property)
    return None

