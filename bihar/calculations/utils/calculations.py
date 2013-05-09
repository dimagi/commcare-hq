def _get_actions(case, action_filter=lambda a: True):
    for action in case.actions:
        if action_filter(action):
            yield action


def get_forms(case, action_filter=lambda a: True, form_filter=lambda f: True):
    for action in _get_actions(case, action_filter=action_filter):
        if getattr(action, 'xform', None) and form_filter(action.xform):
            yield action.xform