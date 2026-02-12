from collections import defaultdict

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
    diff = _convert_update_to_delete_plus_add(diff)
    update = action.update
    conflicts = action.conflicts
    delete_missing = defaultdict(set)

    for prop, questions in diff.get('delete', {}).items():
        for question in questions:
            if not _drop(prop, question['question_path'], update, conflicts):
                delete_missing[prop].add(question['question_path'])

    missing = []
    for prop, questions in diff.get('add', {}).items():
        for question in questions:
            ccu = ConditionalCaseUpdate(question)
            if ccu.question_path in delete_missing[prop]:
                missing.append({'case_property': prop, 'question_path': question['question_path']})
            elif prop not in update or not update[prop].question_path:
                update[prop] = ccu
            elif update[prop].question_path == ccu.question_path:
                update[prop] = ccu
            else:
                # HACK JsonDict.setdefault has a bug, does not return newly set value
                conflicts.setdefault(prop, [])
                conflicts[prop].append(ccu)

    if missing:
        raise MissingPropertyMapException(*missing)


def _drop(prop, path, update, conflicts):
    if prop in update and update[prop].question_path == path:
        if conflicts.get(prop):
            if len(conflicts[prop]) == 1:
                update[prop] = conflicts.pop(prop)[0]
            else:
                update[prop] = conflicts[prop].pop(0)
        else:
            del update[prop]
        return True
    found = [i for i, question in enumerate(conflicts.get(prop, []))
             if question.question_path == path]
    if found:
        if len(conflicts[prop]) == 1:
            del conflicts[prop]
        else:
            del conflicts[prop][found[0]]
    return found


def _convert_update_to_delete_plus_add(diff):
    """update => delete + add

    For backward compatibility with legacy 'update' key in diff, which
    is no longer supported by the merge algorithm. This can be removed
    when all clients (Vellum and case_config_ui.js) have been updated to
    not use the 'update' key.
    """
    if diff.get('update'):
        diff = diff.copy()
        delete = diff['delete'] = diff['delete'].copy() if 'delete' in diff else {}
        add = diff['add'] = diff['add'].copy() if 'add' in diff else {}
        for key, questions in diff.pop('update').items():
            delete[key] = delete[key].copy() if key in delete else []
            delete[key].extend(questions)
            add[key] = add[key].copy() if key in add else []
            add[key].extend(questions)
    return diff


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
        assert not self.action.conflicts
        self.action.name_update = ConditionalCaseUpdate()


class _NameConflictsAdapter:
    def __init__(self, action):
        self.action = action

    def __contains__(self, key):
        _check_name(key)
        return bool(self.action.conflicts)

    def __getitem__(self, key):
        _check_name(key)
        return self.action.conflicts

    def __delitem__(self, key):
        _check_name(key)
        del self.action.conflicts[:]

    def get(self, key, default=None):
        _check_name(key)
        return self.action.conflicts

    def pop(self, key):
        _check_name(key)
        result, self.action.conflicts = self.action.conflicts, []
        return result

    def setdefault(self, key, default):
        _check_name(key)
        return self.action.conflicts


def _check_name(key):
    assert key == 'name', f'Invalid OpenCaseAction field: {key}'
