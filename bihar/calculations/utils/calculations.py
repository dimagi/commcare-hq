def _get_actions(case, action_filter=lambda a: True, reverse=False):
    ordered = reversed if reverse else lambda x: x
    for action in ordered(case.actions):
        if action_filter(action):
            yield action


def get_forms(case, action_filter=lambda a: True, form_filter=lambda f: True,
              reverse=False, yield_action=False):
    if not hasattr(case, '_forms_cache'):
        case._forms_cache = {}
    for action in _get_actions(case, action_filter=action_filter,
                               reverse=reverse):
        if action.xform_id not in case._forms_cache:
            case._forms_cache[action.xform_id] = action.xform
        xform = case._forms_cache[action.xform_id]
        if xform and form_filter(xform):
            if yield_action:
                yield xform, action
            else:
                yield xform