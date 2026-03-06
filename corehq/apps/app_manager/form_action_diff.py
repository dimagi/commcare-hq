from .exceptions import MissingPropertyMapException
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
            if update[prop].question_path == question['question_path']:
                del update[prop]

    for prop, questions in diff.get('update', {}).items():
        for question in questions:
            if update[prop].question_path == question['question_path']:
                update[prop] = ConditionalCaseUpdate(question)
            else:
                raise MissingPropertyMapException

    for prop, questions in diff.get('add', {}).items():
        for question in questions:
            ccu = ConditionalCaseUpdate(question)
            if prop not in update or not update[prop].question_path:
                update[prop] = ccu
            elif update[prop].question_path == ccu.question_path:
                update[prop] = ccu
            else:
                action.conflicts[prop].append(ccu)


class _UpdateCaseAdapter:
    def __init__(self, action):
        self.update = _NameUpdateAdapter(action)
        self.conflicts = _NameConflictsAdapter(action)


class _NameUpdateAdapter:
    def __init__(self, action):
        self.action = action

    def __contains__(self, key):
        _check_name(key)
        return True

    def __getitem__(self, key):
        _check_name(key)
        return self.action.name_update

    def __setitem__(self, key, value):
        _check_name(key)
        self.action.name_update = value

    def __delitem__(self, key):
        _check_name(key)
        if self.action.conflicts:
            self.action.name_update = self.action.conflicts.pop(0)
        else:
            self.action.name_update = ConditionalCaseUpdate()


class _NameConflictsAdapter:
    def __init__(self, action):
        self.action = action

    def __getitem__(self, key):
        _check_name(key)
        return self.action.conflicts


def _check_name(key):
    assert key == 'name', f'Invalid OpenCaseAction field: {key}'
