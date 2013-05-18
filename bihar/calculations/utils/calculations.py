def _get_actions(case, action_filter=lambda a: True, reverse=False):
    ordered = reversed if reverse else lambda x: x
    for action in ordered(case.actions):
        if action_filter(action):
            yield action


def get_forms(case, action_filter=lambda a: True, form_filter=lambda f: True,
              reverse=False):
    for action in _get_actions(case, action_filter=action_filter,
                               reverse=reverse):
        if getattr(action, 'xform', None) and form_filter(action.xform):
            yield action.xform