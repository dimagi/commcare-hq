from .models import ConditionalCaseUpdate


def merge_case_mappings(diff, form_actions):
    """Apply open/update case diffs to form actions

    :param diff: dict. Example:
        {
            "open_case": {
                "add": [{"question_path": "/data/new"}, ...],
                "delete": [{"question_path": "/data/old"}, ...],
            },
            "update_case": {
                "add": {
                    "one": [{"question_path": "/data/first"}, ...],
                    ...
                },
                "delete": {
                    "another": [{"question_path": "/data/other"}, ...],
                    ...
                },
            },
        }
    :param form_actions: FormActions object, will be mutated.
    :raises: KeyError if the diff contained unknown top-level keys. This
        should not happen unless there is a bug in the code or a request
        had an unexpected format (user modified?).
    """
    unknowns = diff.keys() - {'open_case', 'update_case'}
    if unknowns:
        raise KeyError(f"unknown diff keys: {unknowns}")
    if 'open_case' in diff:
        name_diff = {key: {"name": value} for key, value in diff['open_case'].items()}
        _merge(name_diff, _UpdateCaseAdapter(form_actions.open_case))
    if 'update_case' in diff:
        _merge(diff['update_case'], form_actions.update_case)


def _merge(diff, action):
    update = action.update
    for prop, questions in diff.get('delete', {}).items():
        for question in questions:
            del update[prop]

    for prop, questions in diff.get('update', {}).items():
        for question in questions:
            update[prop] = ConditionalCaseUpdate(question)

    for prop, questions in diff.get('add', {}).items():
        for question in questions:
            update[prop] = ConditionalCaseUpdate(question)


class _UpdateCaseAdapter:
    def __init__(self, action):
        self.update = _NameUpdateAdapter(action)


class _NameUpdateAdapter:
    def __init__(self, action):
        self.action = action

    def __getitem__(self, key):
        _check_name(key)
        return self.action.name_update

    def __setitem__(self, key, value):
        _check_name(key)
        self.action.name_update = value

    def __delitem__(self, key):
        _check_name(key)
        self.action.name_update = None


def _check_name(key):
    assert key == 'name', f'Invalid OpenCaseAction field: {key}'
