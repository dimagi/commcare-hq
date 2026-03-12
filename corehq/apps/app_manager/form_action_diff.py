from collections import defaultdict

from .exceptions import MissingPropertyMapException
from .models import ConditionalCaseUpdate


def get_case_mappings(actions):
    """Get FormActions case mappings for Vellum

    :returns: {'<case property>': [{'question_path': ...}, ...], ...}
    """
    def to_json(obj):
        json = obj.to_json()
        if 'doc_type' in json:
            del json['doc_type']
        return json

    data = {}
    if actions.open_case:
        items = [actions.open_case.name_update] + actions.open_case.conflicts
        data.update({'name': [to_json(u) for u in items]})
    if actions.update_case:
        conflicts = actions.update_case.conflicts
        data.update({
            prop: [to_json(u) for u in [update] + conflicts.get(prop, [])]
            for prop, update in actions.update_case.update.items()
        })
    return data


def from_combined_diff(combined_diff, *, is_registration):
    """Convert Vellum case mapping diff to `merge_case_mappings` structure"""
    data = combined_diff.copy()
    diff = {'update_case': data}
    if is_registration:
        open_diff = diff['open_case'] = {}
        for key in ['add', 'update', 'delete']:
            if key in data and 'name' in data[key]:
                data[key] = data[key].copy()
                open_diff[key] = data[key].pop('name')
    return diff


def make_multi(actions_json):
    """Convert FormActions JSON to case_config_ui.js structure

    Each ConditionalCaseUpdate and related conflicts are merged into a
    "multi" list, which is easier to use in front end code.
    """
    data = actions_json.copy()
    open_case = data.get('open_case')
    if open_case and 'name_update' in open_case:
        open_case = data['open_case'] = open_case.copy()
        open_case['name_update_multi'] = [open_case.pop('name_update')]
        open_case['name_update_multi'].extend(open_case.pop('conflicts', []))
    update_case = data.get('update_case')
    if update_case and 'update' in update_case:
        update_case = data['update_case'] = update_case.copy()
        update_case['update_multi'] = {k: [v] for k, v in update_case.pop('update').items()}
        for key, values in update_case.pop('conflicts', {}).items():
            update_case['update_multi'].setdefault(key, []).extend(values)
    return data


def update_form_actions(form_actions, actions_json, case_mapping_diff):
    """Update FormActions with values from actions_json and case_mapping_diff

    Accepts JSON data from case_config_ui.js

    :param form_actions: FormActions object, will be mutated.
    :param actions_json: dict as produced by `make_multi`.
    :param case_mapping_diff: dict - see `merge_case_mappings`.
    :raises: AttributeError if `actions_json` contains unknown
        properties. This should not happen unless there is a bug in the
        code or a request had an unexpected format (user modified?).
    :raises: KeyError - see `merge_case_mappings`.
    """
    unmulti_json = _drop_multi_updates(actions_json)
    _set_raw_values(form_actions, unmulti_json, {'update_case', 'open_case'})
    if case_mapping_diff:
        merge_case_mappings(case_mapping_diff, form_actions)


def _drop_multi_updates(multi_json):
    # Near opposite of make_multi: case_config_ui.js JSON -> FormActions structure
    data = multi_json.copy()
    open_case = data.get('open_case')
    if open_case:
        open_case = data['open_case'] = open_case.copy()
        for key in ['name_update_multi', 'name_update', 'conflicts']:
            open_case.pop(key, None)
    update_case = data.get('update_case')
    if update_case:
        update_case = data['update_case'] = update_case.copy()
        for key in ['update_multi', 'update', 'conflicts']:
            update_case.pop(key, None)
    return data


def _set_raw_values(obj, data, recurse_on=()):
    for attr, value in data.items():
        if attr not in obj:
            raise AttributeError(f"invalid property: {attr}")
        if attr in recurse_on:
            _set_raw_values(getattr(obj, attr), value)
        else:
            obj.set_raw_value(attr, value)


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
