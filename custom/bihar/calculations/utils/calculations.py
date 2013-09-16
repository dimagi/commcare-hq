from casexml.apps.case.models import CommCareCase


def get_actions(case, action_filter=lambda a: True, reverse=False):
    ordered = reversed if reverse else lambda x: x
    for action in ordered(case.actions):
        if action_filter(action):
            yield action


def get_forms(case, action_filter=lambda a: True, form_filter=lambda f: True,
              reverse=False, yield_action=False):
    if not hasattr(case, '_forms_cache'):
        case._forms_cache = {}
    for action in get_actions(case, action_filter=action_filter,
                               reverse=reverse):
        if action.xform_id not in case._forms_cache:
            case._forms_cache[action.xform_id] = action.xform
        xform = case._forms_cache[action.xform_id]
        if xform and form_filter(xform):
            if yield_action:
                yield xform, action
            else:
                yield xform


def get_form(case, action_filter=lambda a: True, form_filter=lambda f: True, reverse=False):
    """
    returns the first form that passes through both filter functions
    """
    gf = get_forms(case, action_filter=action_filter, form_filter=form_filter, reverse=reverse)
    try:
        return gf.next()
    except StopIteration:
        return None


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