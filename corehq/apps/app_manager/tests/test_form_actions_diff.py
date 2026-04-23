from copy import deepcopy

import pytest
from django.test import SimpleTestCase

from ..form_action_diff import (
    _convert_update_to_delete_plus_add,
    from_combined_diff,
    get_case_mappings,
    merge_case_mappings,
    make_multi,
    update_form_actions,
    _drop_multi_updates,
)
from ..models import (
    FormActions, UpdateCaseAction, OpenCaseAction
)
from ..views.forms import _case_mapping_diff_has_changes


class OpenCaseActionApplyDiffTests(SimpleTestCase):

    def test_no_changes(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': '/data/name'}}))

        merge_case_mappings({}, actions)
        action = actions.open_case

        assert action.name_update.question_path == '/data/name'

    def test_add_mapping_with_different_question_path_creates_conflict(self):
        # added "/data/new_name" mapping should conflict with existing "/data/name" mapping
        actions = FormActions(open_case=OpenCaseAction({
            'name_update': {'question_path': '/data/name'},
        }))

        diff = {'open_case': {'add': [{'question_path': '/data/new_name'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        multi_paths = [update.question_path for update in [action.name_update] + action.conflicts]
        assert multi_paths == ['/data/name', '/data/new_name']

    def test_conflicting_name_addition_is_overwritten(self):
        # added "/name" mapping should overwrite existing "/name" mapping
        actions = FormActions(open_case=OpenCaseAction({
            'name_update': {'question_path': '/data/name', 'update_mode': 'always'},
        }))

        diff = {'open_case': {'add': [{'question_path': '/data/name', 'update_mode': 'edit'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == '/data/name'
        assert action.name_update.update_mode == 'edit'
        assert not action.conflicts

    def test_merge_case_mappings_remove_name(self):
        actions = FormActions(open_case=OpenCaseAction.wrap({
            'name_update_multi': [{'question_path': '/data/name1'}, {'question_path': '/data/name2'}]
        }))

        diff = {'open_case': {'delete': [{'question_path': '/data/name1'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == '/data/name2'

    def test_merge_case_mappings_delete_mapping_does_nothing_when_the_mapping_is_absent(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': '/data/name2'}}))

        diff = {'open_case': {'delete': [{'question_path': '/data/name1'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == '/data/name2'

    def test_merge_case_mappings_update_mode(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': '/data/name'}}))

        diff = {'open_case': {'update': [{'question_path': '/data/name', 'update_mode': 'edit'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.update_mode == 'edit'

    def test_merge_case_mappings_updating_missing_name_raises_error(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': '/data/name'}}))

        diff = {'open_case': {'update': [{'question_path': '/data/missing_name', 'update_mode': 'edit'}]}}
        merge_case_mappings(diff, actions)

        assert [c.question_path for c in actions.open_case.conflicts] == ['/data/missing_name']

    def test_merge_case_mappings_remove_conflicted_name(self):
        actions = FormActions(open_case=OpenCaseAction({
            'name_update': {'question_path': '/data/name1'},
            'conflicts': [{'question_path': '/data/name2'}, {'question_path': '/data/name3'}],
        }))

        diff = {'open_case': {'delete': [{'question_path': '/data/name1'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == '/data/name2'
        assert action.conflicts[0].question_path == '/data/name3'
        assert len(action.conflicts) == 1

    def test_delete_conflict(self):
        action = OpenCaseAction({
            'name_update': {'question_path': '/data/name1'},
            'conflicts': [{'question_path': '/data/name2'}],
        })
        form_actions = FormActions(open_case=action)

        diff = {'open_case': {'delete': [{'question_path': '/data/name2'}]}}
        merge_case_mappings(diff, form_actions)

        assert action.name_update.question_path == '/data/name1'
        assert not action.conflicts

    def test_delete_one_of_multiple_conflicts(self):
        action = OpenCaseAction({
            'name_update': {'question_path': '/data/name1'},
            'conflicts': [{'question_path': '/data/name2'}, {'question_path': '/data/name3'}],
        })
        form_actions = FormActions(open_case=action)

        diff = {'open_case': {'delete': [{'question_path': '/data/name2'}]}}
        merge_case_mappings(diff, form_actions)

        assert action.name_update
        assert action.conflicts[0].question_path == '/data/name3'
        assert len(action.conflicts) == 1


class UpdateCaseActionApplyDiffTests(SimpleTestCase):

    def test_no_changes(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'}
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({}, form_actions)

        assert actions.update['one'].question_path == '/data/one'

    def test_add_value_no_conflict(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'},
            'two': {'question_path': '/data/two'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'three': [{'question_path': '/data/some_path'}]},
        }}, form_actions)

        assert set(actions.update.keys()) == {'one', 'two', 'three'}

    def test_add_value_creates_conflict(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/question1'}
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': '/data/question2'}]}
        }}, form_actions)

        assert set(self._conflicting(actions)) == {'one'}
        paths = {c.question_path for c in self._conflicting(actions)['one']}
        assert paths == {'/data/question1', '/data/question2'}

    def test_add_value_with_legacy_update_multi_conflict(self):
        form_actions = FormActions({'update_case': {'update_multi': {
            'one': [{'question_path': '/data/question1'}, {'question_path': '/data/question2'}]
        }}})

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': '/data/question3'}]}
        }}, form_actions)
        actions = form_actions.update_case

        assert set(actions.conflicts) == {'one'}
        paths = [update.question_path for update in self._conflicting(actions)['one']]
        assert set(paths) == {'/data/question1', '/data/question2', '/data/question3'}

    def test_add_value_with_existing_conflict(self):
        actions = UpdateCaseAction({
            'update': {'one': {'question_path': '/data/question1'}},
            'conflicts': {'one': [{'question_path': '/data/question2'}]}
        })
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': '/data/question3'}]}
        }}, form_actions)

        assert set(actions.conflicts) == {'one'}
        paths = [update.question_path for update in self._conflicting(actions)['one']]
        assert set(paths) == {'/data/question1', '/data/question2', '/data/question3'}

    def test_adding_duplicate_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/question1'}
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': '/data/question1'}]}
        }}, form_actions)

        assert set(actions.update.keys()) == {'one'}
        assert actions.update['one'].question_path == '/data/question1'

    def test_adding_existing_modified_property_overwrites_the_property(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one', 'update_mode': 'always'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': '/data/one', 'update_mode': 'edit'}]},
        }}, form_actions)

        assert actions.update['one'].update_mode == 'edit'

    def test_remove_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'},
            'two': {'question_path': '/data/two'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': '/data/one'}]},
        }}, form_actions)

        assert set(actions.update.keys()) == {'two'}

    def test_deleting_a_missing_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': '/data/two'}]}
        }}, form_actions)

        assert actions.update.keys() == {'one'}
        assert actions.update['one'].question_path == '/data/one'

    def test_update_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one', 'update_mode': 'always'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'update': {
                'one': [{'question_path': '/data/one', 'update_mode': 'edit'}],
            }
        }}, form_actions)

        assert actions.update['one'].update_mode == 'edit'

    def test_updating_a_missing_property_adds_a_conflict(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'update': {'two': [{'question_path': '/data/two', 'update_mode': 'edit'}]}
        }}, form_actions)

        assert 'two' not in actions.update
        assert [c.question_path for c in actions.conflicts['two']] == ['/data/two']

    def test_updating_a_missing_question_adds_a_conflict(self):
        # If the specific mapping was deleted by a different session, updating it shouldn't restore it
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'}
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'update': {
                'one': [{'question_path': '/data/two', 'update_mode': 'edit'}]
            }
        }}, form_actions)

        assert actions.update['one'].question_path == '/data/one'
        assert [c.question_path for c in actions.conflicts['one']] == ['/data/two']

    def test_delete_conflict(self):
        actions = UpdateCaseAction({'conflicts': {'one': [{'question_path': '/data/one'}]}})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': '/data/one', 'conflicting_delete': True}]},
        }}, form_actions)

        assert not actions.update
        assert not actions.conflicts

    def test_delete_removes_conflict(self):
        actions = UpdateCaseAction({
            'update': {'one': {'question_path': '/data/one'}},
            'conflicts': {'one': [{'question_path': '/data/two'}]},
        })
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': '/data/one'}]},
        }}, form_actions)

        assert actions.update['one'].question_path == '/data/two'
        assert not actions.conflicts

    def test_multiple_actions_attempting_to_affect_the_same_key_updates_action(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'},
            'two': {'question_path': '/data/two'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'two': [{'question_path': '/data/two'}]},
            'add': {'two': [{'question_path': '/data/two', 'update_mode': 'edit'}]},
        }}, form_actions)

        assert actions.update['one'].question_path == '/data/one'
        assert actions.update['one'].update_mode == 'always'
        assert actions.update['two'].question_path == '/data/two'
        assert actions.update['two'].update_mode == 'edit'
        assert not actions.conflicts

    @staticmethod
    def _conflicting(action):
        assert not set(action.conflicts) - action.update.keys()
        return {
            prop: [item] + action.conflicts.get(prop, [])
            for prop, item in action.update.items()
        }


class FormActionsTests(SimpleTestCase):

    def test_constructor_creates_empty_values(self):
        actions = FormActions()
        assert actions.update_case.update == {}

    def test_all_property_names(self):
        actions = FormActions()
        assert actions.all_property_names() == set()

    def test_all_property_names_adds_update_case_names(self):
        update_case = UpdateCaseAction({'update': {'one': {'question_path': '/data/two'}}})
        actions = FormActions(update_case=update_case)
        assert actions.all_property_names() == {'one'}

    def test_get_case_mappings_serializes_all_updates(self):
        actions = FormActions(
            open_case=OpenCaseAction({
                'name_update': {'question_path': '/data/name1'},
                'conflicts': [{'question_path': '/data/name2'}],
            }),
            update_case=UpdateCaseAction({
                'update': {
                    'one': {'question_path': '/A/'},
                    'two': {'question_path': '/C/'},
                },
                'conflicts': {
                    'one': [{'question_path': '/B/'}, {'question_path': '/D/'}],
                    'three': [{'question_path': '/E/'}],
                }
            }),
        )

        json = get_case_mappings(actions)

        assert json == {
            'name': [
                {'question_path': '/data/name1', 'update_mode': 'always'},
                {'question_path': '/data/name2', 'update_mode': 'always'},
            ],
            'one': [
                {'question_path': '/A/', 'update_mode': 'always'},
                {'question_path': '/B/', 'update_mode': 'always'},
                {'question_path': '/D/', 'update_mode': 'always'},
            ],
            'two': [{'question_path': '/C/', 'update_mode': 'always'}],
            'three': [
                {'question_path': '/E/', 'update_mode': 'always', 'conflicting_delete': True},
            ],
        }

    def test_get_case_mappings_with_conflicts_and_concurrent_delete(self):
        actions = FormActions(
            open_case=OpenCaseAction({'name_update': {'question_path': '/data/name'}}),
            update_case=UpdateCaseAction({
                'update': {},
                'conflicts': {
                    'one': [{'question_path': '/A/'}, {'question_path': '/B/'}],
                }
            }),
        )

        json = get_case_mappings(actions)

        assert json == {
            'name': [{'question_path': '/data/name', 'update_mode': 'always'}],
            'one': [
                {'question_path': '/A/', 'update_mode': 'always', 'conflicting_delete': True},
                {'question_path': '/B/', 'update_mode': 'always', 'conflicting_delete': True},
            ],
        }

    def test_merge_case_mappings_raises_on_unrecognized_key(self):
        actions = FormActions()
        diff = {'malicious_key': {'update': {}}}

        with pytest.raises(KeyError):
            merge_case_mappings(diff, actions)

    def test_merge_empty_diff(self):
        actions = FormActions(
            open_case=OpenCaseAction({
                'name_update': {'question_path': '/data/name'},
            }),
            update_case=UpdateCaseAction({
                'update': {
                    'one': {'question_path': '/data/one'},
                    'two': {'question_path': '/data/two'},
                }
            }),
        )
        snapshot = actions.to_json()

        merge_case_mappings({}, actions)

        assert actions['open_case']['name_update']['question_path'] == '/data/name'
        assert list(actions['update_case']['update'].keys()) == ['one', 'two']
        assert actions.to_json() == snapshot

    def test_merge_case_mappings_with_all_actions_at_once(self):
        actions = FormActions(
            open_case=OpenCaseAction({
                'name_update': {'question_path': '/data/old_name'},
            }),
            update_case=UpdateCaseAction({
                'update': {
                    'one': {'question_path': '/data/one'},
                    'two': {'question_path': '/data/two'},
                }
            }),
        )

        merge_case_mappings({
            'open_case': {
                'add': [{'question_path': '/data/new_name'}],
                'delete': [{'question_path': '/data/old_name'}],
            },
            'update_case': {
                'add': {'three': [{'question_path': '/data/three'}]},
                'delete': {'one': [{'question_path': '/data/one'}]},
                'update': {
                    'two': [{'question_path': '/data/two', 'update_mode': 'edit'}]
                }
            }
        }, actions)

        assert actions.open_case.name_update.question_path == '/data/new_name'
        assert set(actions.update_case.update.keys()) == {'two', 'three'}
        assert actions.update_case.update['two'].update_mode == 'edit'

    def test_merge_case_mappings_with_double_addition(self):
        # A scenario that would have previously caused DiffConflictException:
        # update + add => delete + add + add (last add wins)
        # Edge case is probably not possible to create in real life,
        # although a bug allowed it in the past.
        actions = FormActions(
            open_case=OpenCaseAction({
                'name_update': {'question_path': '/data/form_name'},
            }),
            update_case=UpdateCaseAction({
                'update': {
                    'one': {'question_path': '/data/one'},
                    'two': {'question_path': '/data/two'},
                }
            }),
        )

        merge_case_mappings({
            'open_case': {
                'delete': [{'question_path': '/data/form_name'}],
                'add': [
                    {'question_path': '/data/form_name', 'update_mode': 'always'},
                    {'question_path': '/data/form_name', 'update_mode': 'edit'}
                ],
            },
            'update_case': {
                'delete': {'one': [{'question_path': '/data/one'}]},
                'add': {'one': [
                    {'question_path': '/data/one', 'update_mode': 'always'},
                    {'question_path': '/data/one', 'update_mode': 'edit'},
                ]},
            },
        }, actions)

        assert actions.open_case.name_update.question_path == '/data/form_name'
        assert actions.open_case.name_update.update_mode == 'edit'
        assert not actions.open_case.conflicts
        assert actions.update_case.update['one'].question_path == '/data/one'
        assert actions.update_case.update['one'].update_mode == 'edit'
        assert not actions.update_case.conflicts

    def test_merge_case_mappings_with_double_deletion(self):
        # a scenario that would have previously caused DiffConflictException
        # delete + update => delete + delete + add (conflicting delete)
        actions = FormActions(update_case=UpdateCaseAction({'update': {
            'one': {'question_path': '/data/one'},
            'two': {'question_path': '/data/two'},
        }}))

        merge_case_mappings({
            'update_case': {
                'delete': {'one': [
                    {'question_path': '/data/one'},
                    {'question_path': '/data/one', 'update_mode': 'edit'},
                ]},
                'add': {'one': [
                    {'question_path': '/data/one', 'update_mode': 'edit'}
                ]},
            },
        }, actions)

        assert 'one' not in actions.update_case.update
        conflict, = actions.update_case.conflicts['one']
        assert conflict.question_path == '/data/one'
        assert conflict.update_mode == 'edit'

    def test_merge_case_mappings_with_conflicting_delete(self):
        actions = FormActions(update_case=UpdateCaseAction({
            'update': {
                'one': {'question_path': '/data/one', 'update_mode': 'always'},
                'two': {'question_path': '/data/two'},
            }
        }))

        merge_case_mappings({
            'update_case': {
                'delete': {'one': [
                    {'question_path': '/data/one', 'update_mode': 'edit'},
                ]},
            },
        }, actions)

        assert 'one' not in actions.update_case.update
        conflict, = actions.update_case.conflicts['one']
        assert conflict.question_path == '/data/one'
        assert conflict.update_mode == 'always'

    def test_merge_case_mappings_already_deleted(self):
        actions = FormActions(update_case=UpdateCaseAction({
            'update': {
                'two': {'question_path': '/data/two'},
            }
        }))

        merge_case_mappings({
            'update_case': {
                'delete': {'one': [
                    {'question_path': '/data/one', 'update_mode': 'edit'},
                ]},
            },
        }, actions)

        assert 'one' not in actions.update_case.update
        assert 'one' not in actions.update_case.conflicts

    def test_update_form_actions_with_conditional_update(self):
        action = OpenCaseAction({'name_update': {'question_path': '/data/name'}})
        form_actions = FormActions(open_case=action)
        actions_json = {
            'open_case': {'condition': {'type': 'if', 'question': 'name', 'answer': 'bob', 'operator': '='}}
        }

        update_form_actions(form_actions, actions_json, {})

        assert action.condition.type == 'if'
        assert action.condition.question == 'name'
        assert action.condition.answer == 'bob'
        assert action.condition.operator == '='

    def test_update_form_actions_ignores_direct_name_update(self):
        action = OpenCaseAction({'name_update': {'question_path': '/data/name'}})
        form_actions = FormActions(open_case=action)
        actions_json = {'open_case': {'name_update': {'question_path': '/data/name2'}}}

        update_form_actions(form_actions, actions_json, {})

        assert action.name_update.question_path == '/data/name'
        assert not action.conflicts

    def test_update_form_actions_ignores_direct_name_update_multi(self):
        action = OpenCaseAction({'name_update': {'question_path': '/data/name'}})
        form_actions = FormActions(open_case=action)
        actions_json = {'open_case': {'name_update_multi': [{'question_path': '/data/name2'}]}}

        update_form_actions(form_actions, actions_json, {})

        assert action.name_update.question_path == '/data/name'
        assert not action.conflicts

    def test_update_form_actions_with_invalid_key_raises_exception(self):
        action = OpenCaseAction({'name_update': {'question_path': '/data/name'}})
        form_actions = FormActions(open_case=action)
        actions_json = {"open_case": {'invalid_property': {}}}

        with pytest.raises(AttributeError):
            update_form_actions(form_actions, actions_json, {})

    def test_update_form_actions_ignores_direct_updates(self):
        actions = UpdateCaseAction({'update': {'one': {'question_path': '/data/one'}}})
        form_actions = FormActions(update_case=actions)
        actions_json = {'update_case': {'update': {'one': {'question_path': '/data/two'}}}}

        update_form_actions(form_actions, actions_json, {})

        assert actions.update['one'].question_path == '/data/one'
        assert not actions.conflicts

    def test_update_form_actions_ignores_direct_update_multi(self):
        actions = UpdateCaseAction({'update': {'one': {'question_path': '/data/one'}}})
        form_actions = FormActions(update_case=actions)
        actions_json = {'update_case': {'update_multi': {'one': {'question_path': '/data/two'}}}}

        update_form_actions(form_actions, actions_json, {})

        assert actions.update['one'].question_path == '/data/one'
        assert not actions.conflicts

    def test_update_form_actions_updates_condition(self):
        actions = UpdateCaseAction()
        form_actions = FormActions(update_case=actions)
        actions_json = {'update_case': {'condition': {'type': 'never'}}}

        update_form_actions(form_actions, actions_json, {})

        assert actions.condition.type == 'never'

    def test_update_form_actions_with_other_updates(self):
        # i.e. not open_case or update_case
        form_actions = FormActions()
        close_case_update = {'close_case': {'condition': {'type': 'never'}}}

        update_form_actions(form_actions, close_case_update, {})

        assert form_actions.close_case.condition.type == 'never'


class CaseMappingDiffHasChangesTests(SimpleTestCase):

    def test_none(self):
        assert not _case_mapping_diff_has_changes(None)

    def test_empty(self):
        assert not _case_mapping_diff_has_changes({})

    def test_empty_open_case(self):
        assert not _case_mapping_diff_has_changes({"open_case": {}})

    def test_empty_update_case(self):
        assert not _case_mapping_diff_has_changes({"update_case": {}})

    def test_both_empty(self):
        assert not _case_mapping_diff_has_changes({"open_case": {}, "update_case": {}})

    def test_empty_actions(self):
        assert not _case_mapping_diff_has_changes({
            "open_case": {"add": [], "delete": []},
            "update_case": {"add": {}, "delete": {}},
        })

    def test_has_changes(self):
        diff = {
            'open_case': {
                'delete': [{'question_path': '/data/old_name'}],
                'add': [{'question_path': '/data/new_name'}],
            },
            'update_case': {
                'delete': {'one': [{'question_path': '/data/one'}]},
                'add': {'two': [{'question_path': '/data/two'}]},
            }
        }

        assert _case_mapping_diff_has_changes(diff)


class ConvertUpdateToAddPlusDeleteTests(SimpleTestCase):
    # 'update' key in diff is for backward compatibility

    def test_simple_update(self):
        diff = {'update': {'one': [{'question_path': '/data/one'}]}}
        snapshot = deepcopy(diff)

        new_diff = _convert_update_to_delete_plus_add(diff)

        assert new_diff == {
            'delete': {'one': [{'question_path': '/data/one'}]},
            'add': {'one': [{'question_path': '/data/one'}]},
        }
        assert diff == snapshot, 'original diff should not be mutated'

    def test_update_with_add_and_delete(self):
        diff = {
            'add': {'one': [{'question_path': '/data/add'}]},
            'delete': {'one': [{'question_path': '/data/del'}]},
            'update': {'one': [{'question_path': '/data/upd'}]},
        }
        snapshot = deepcopy(diff)

        new_diff = _convert_update_to_delete_plus_add(diff)

        assert new_diff == {
            'delete': {'one': [
                {'question_path': '/data/del'},
                {'question_path': '/data/upd'},
            ]},
            'add': {'one': [
                {'question_path': '/data/add'},
                {'question_path': '/data/upd'},
            ]},
        }
        assert diff == snapshot, 'original diff should not change'


class CombinedDiffTests(SimpleTestCase):

    def test_from_combined_diff_non_registration_name_stays_in_update(self):
        combined_diff = {
            'add': {
                'name': [{'question_path': '/data/one'}],
                'other': [{'question_path': '/data/two'}],
            },
            'update': {
                'name': [{'question_path': '/data/three'}],
                'other': [{'question_path': '/data/four'}],
            },
            'delete': {
                'name': [{'question_path': '/data/five'}],
                'other': [{'question_path': '/data/six'}],
            },
        }
        snapshot = deepcopy(combined_diff)

        diff = from_combined_diff(combined_diff, is_registration=False)

        assert not diff.get('open_case')
        assert diff['update_case'] == combined_diff
        assert combined_diff == snapshot, 'combined_diff should not be mutated'

    def test_from_combined_diff_registration_name_is_in_open_case(self):
        combined_diff = {
            'add': {
                'name': [{'question_path': '/data/one'}],
                'other': [{'question_path': '/data/two'}],
            },
            'update': {
                'name': [{'question_path': '/data/three'}],
                'other': [{'question_path': '/data/four'}],
            },
            'delete': {
                'name': [{'question_path': '/data/five'}],
                'other': [{'question_path': '/data/six'}],
            },
        }
        snapshot = deepcopy(combined_diff)

        diff = from_combined_diff(combined_diff, is_registration=True)

        assert diff['open_case'] == {
            'add': [{'question_path': '/data/one'}],
            'update': [{'question_path': '/data/three'}],
            'delete': [{'question_path': '/data/five'}],
        }
        assert diff['update_case'] == {
            'add': {'other': [{'question_path': '/data/two'}]},
            'update': {'other': [{'question_path': '/data/four'}]},
            'delete': {'other': [{'question_path': '/data/six'}]},
        }
        assert combined_diff == snapshot, 'combined_diff should not be mutated'


class TestMultiTools(SimpleTestCase):

    def test_make_multi(self):
        actions_json = FormActions(
            open_case=OpenCaseAction({
                'name_update': {'question_path': '/data/form_name'},
                'conflicts': [{'question_path': '/data/other_name'}],
            }),
            update_case=UpdateCaseAction({
                'update': {
                    'one': {'question_path': '/data/one'},
                    'two': {'question_path': '/data/two'},
                },
                'conflicts': {
                    'one': [{'question_path': '/data/other_one'}],
                    'two': [{'question_path': '/data/other_two'}],
                    'three': [{'question_path': '/data/three'}],
                },
            }),
            usercase_update=UpdateCaseAction({
                'update': {
                    'one': {'question_path': '/data/test_path'},
                },
            }),
        ).to_json()
        snapshot = deepcopy(actions_json)

        multi = make_multi(actions_json)

        assert multi['open_case'] == _Subdict({
            'name_update_multi': [
                _Subdict({'question_path': '/data/form_name'}),
                _Subdict({'question_path': '/data/other_name'}),
            ],
        })
        assert multi['update_case'] == _Subdict({
            'update_multi': {
                'one': [
                    _Subdict({'question_path': '/data/one'}),
                    _Subdict({'question_path': '/data/other_one'}),
                ],
                'two': [
                    _Subdict({'question_path': '/data/two'}),
                    _Subdict({'question_path': '/data/other_two'}),
                ],
                'three': [
                    _Subdict({'question_path': '/data/three', 'conflicting_delete': True}),
                ]
            },
        })
        assert 'usercase_update' in multi
        assert multi['usercase_update'].get('update')
        assert actions_json == snapshot, 'actions_json should not be mutated'

    def test_make_multi_with_conflicts_and_concurrent_delete(self):
        actions_json = FormActions(
            update_case=UpdateCaseAction({
                'update': {},
                'conflicts': {
                    'one': [
                        {'question_path': '/data/two'},
                        {'question_path': '/data/other_two'},
                    ],
                },
            }),
        ).to_json()
        snapshot = deepcopy(actions_json)

        multi = make_multi(actions_json)

        assert multi['update_case'] == _Subdict({
            'update_multi': {
                'one': [
                    _Subdict({'question_path': '/data/two', 'conflicting_delete': True}),
                    _Subdict({'question_path': '/data/other_two', 'conflicting_delete': True}),
                ]
            },
        })
        assert actions_json == snapshot, 'actions_json should not be mutated'

    def test_unmake_multi(self):
        input_json = {
            'open_case': {
                'external_id': '0000',
                'name_update_multi': [
                    {'question_path': '/data/form_name'},
                    {'question_path': '/data/other_name'},
                ],
                'name_update': {},
                'conflicts': [],
            },
            'update_case': {
                'condition': {'type': 'never'},
                'update_multi': {
                    'one': [{'question_path': '/data/one'}, {'question_path': '/data/other_one'}],
                    'two': [{'question_path': '/data/two'}, {'question_path': '/data/other_two'}],
                },
                'update': {},
                'conflicts': {},
            },
            'usercase_update': {
                'update': {
                    'one': {'question_path': '/data/test_path'},
                },
            },
        }
        snapshot = deepcopy(input_json)

        output_json = _drop_multi_updates(input_json)

        assert output_json == {
            'open_case': {'external_id': '0000'},
            'update_case': {'condition': {'type': 'never'}},
            'usercase_update': {
                'update': {
                    'one': {'question_path': '/data/test_path'},
                },
            },
        }
        assert input_json == snapshot, 'input json should not be modified'


class _Subdict(dict):

    def __eq__(self, other):
        if not isinstance(other, dict):
            return super().__eq__(other)
        # ignore key/value pairs in other but not in self
        for key, value in self.items():
            if key not in other or value != other[key]:
                return False
        return True
