from casexml.apps.case.models import CommCareCase

def any_action_property(action, props):
    for p in props:
        if p in action.updated_unknown_properties and action.updated_unknown_properties[p]:
            return True
    return False

def visit_is(action, visit_type):
    """
    for a given action returns whether it's a visit of the type
    """
    return action.updated_unknown_properties.get('last_visit_type', None) == visit_type

def has_visit(case, type):
    """
    returns whether a visit of a type exists in the case
    """
    return len(filter(lambda a: visit_is(a, type), case.actions)) > 0

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

