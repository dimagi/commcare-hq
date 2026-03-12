from copy import deepcopy

import pytest
from django.test import SimpleTestCase

from ..exceptions import (
    MissingPropertyMapException,
    InvalidPropertyException
)
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
    FormActions, UpdateCaseAction, OpenCaseAction, OpenCaseDiff, UpdateCaseDiff, FormActionsDiff
)


class UpdateableDocumentTests(SimpleTestCase):
    def test_handles_partially_specified_update(self):
        actions = FormActions()
        updates = {
            'usercase_update': {
                'update': {
                    'one': {
                        'question_path': 'test_path',
                        'update_mode': 'edit',
                    }
                },
                'condition': {
                    'type': 'always',
                    'question': 'test_question',
                    'answer': 'yes',
                    'operator': 'selected'
                }
            }
        }

        actions.update_object(updates)

        # Verify that empty values remain empty
        assert actions.update_case.update == {}

        # Verify that the updated values were applied
        assert set(actions.usercase_update.update.keys()) == {'one'}
        assert actions.usercase_update.update['one'].question_path == 'test_path'
        assert actions.usercase_update.update['one'].update_mode == 'edit'

        assert actions.usercase_update.condition['type'] == 'always'
        assert actions.usercase_update.condition['question'] == 'test_question'
        assert actions.usercase_update.condition['answer'] == 'yes'
        assert actions.usercase_update.condition['operator'] == 'selected'

    def test_throws_error_on_unrecognized_key(self):
        actions = FormActions()
        updates = {
            'malicious_key': {
                'update': {}
            }
        }

        with pytest.raises(InvalidPropertyException) as context:
            actions.update_object(updates)

        assert context.value.invalid_property == 'malicious_key'


class OpenCaseActionTests(SimpleTestCase):
    def test_construction(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        assert action.name_update.question_path == 'name'

    def test_multiple_name_updates(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })
        multi_paths = [update.question_path for update in action.name_update_multi]
        assert multi_paths == ['name1', 'name2']

    def test_make_multi_populates_multi(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name'}
        })

        action.make_multi()

        multi_paths = [update.question_path for update in action.name_update_multi]
        assert multi_paths == ['name']
        assert action.name_update is None

    def test_make_multi_does_nothing_when_update_multi_already_exists(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'one'}, {'question_path': 'two'}]
        })

        action.make_multi()

        multi_paths = [update.question_path for update in action.name_update_multi]
        assert multi_paths == ['one', 'two']
        assert action.name_update.question_path is None

    def test_normalize_name_update_when_multiple_updates_exist_does_nothing(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })

        action.normalize_name_update()

        assert action.name_update.question_path is None
        multi_paths = [update.question_path for update in action.name_update_multi]
        assert multi_paths == ['name1', 'name2']

    def test_normalize_name_update_moves_name_update_multi_to_name_update(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name'}]
        })

        action.normalize_name_update()

        assert action.name_update.question_path == 'name'
        assert action.name_update_multi == []

    def test_make_single_does_nothing_when_name_update_multi_is_empty(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name'}
        })

        action.make_single()
        assert action.name_update.question_path == 'name'
        assert action.name_update_multi == []

    def test_make_single_takes_the_last_entry_for_conflicting_case_properties(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })

        action.make_single()
        assert action.name_update.question_path == 'name2'
        assert action.name_update_multi == []

    def test_has_name_update_returns_true_with_name_update(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name'}
        })

        assert action.has_name_update()

    def test_has_name_update_returns_false_with_empty_path(self):
        action = OpenCaseAction({
            'name_update': {'question_path': ''}
        })

        assert not action.has_name_update()

    def test_has_name_update_looks_at_name_update_multi(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })

        assert action.has_name_update()

    def test_has_name_update_requires_name_update_multi_to_have_a_path(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': ''}]
        })

        assert not action.has_name_update()


class OpenCaseActionApplyDiffTests(SimpleTestCase):

    def test_no_changes(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': 'name'}}))

        merge_case_mappings({}, actions)
        action = actions.open_case

        assert action.name_update.question_path == 'name'

    def test_name_update(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': 'name'}}))

        diff = {'open_case': {'add': [{'question_path': 'new_name'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        multi_paths = [update.question_path for update in [action.name_update] + action.conflicts]
        assert multi_paths == ['name', 'new_name']

    def test_conflicting_name_addition_is_overwritten(self):
        actions = FormActions(open_case=OpenCaseAction({
            'name_update': {'question_path': 'name', 'update_mode': 'always'},
        }))

        diff = {'open_case': {'add': [{'question_path': 'name', 'update_mode': 'edit'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == 'name'
        assert action.name_update.update_mode == 'edit'

    def test_merge_case_mappings_remove_name(self):
        actions = FormActions(open_case=OpenCaseAction.wrap({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        }))

        diff = {'open_case': {'delete': [{'question_path': 'name1'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == 'name2'

    def test_merge_case_mappings_remove_name_does_nothing_when_name_is_absent(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': 'name2'}}))

        diff = {'open_case': {'delete': [{'question_path': 'name1'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == 'name2'

    def test_merge_case_mappings_update_mode(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': 'name'}}))

        diff = {'open_case': {'update': [{'question_path': 'name', 'update_mode': 'edit'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.update_mode == 'edit'

    def test_merge_case_mappings_updating_missing_name_raises_error(self):
        actions = FormActions(open_case=OpenCaseAction({'name_update': {'question_path': 'name'}}))

        with pytest.raises(MissingPropertyMapException):
            diff = {'open_case': {'update': [{'question_path': 'missing_name', 'update_mode': 'edit'}]}}
            merge_case_mappings(diff, actions)

    def test_merge_case_mappings_remove_conflicted_name(self):
        actions = FormActions(open_case=OpenCaseAction({
            'name_update': {'question_path': 'name1'},
            'conflicts': [{'question_path': 'name2'}, {'question_path': 'name3'}],
        }))

        diff = {'open_case': {'delete': [{'question_path': 'name1'}]}}
        merge_case_mappings(diff, actions)
        action = actions.open_case

        assert action.name_update.question_path == 'name2'
        assert action.conflicts[0].question_path == 'name3'
        assert len(action.conflicts) == 1

    def test_delete_conflict(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name1'},
            'conflicts': [{'question_path': 'name2'}],
        })
        form_actions = FormActions(open_case=action)

        diff = {'open_case': {'delete': [{'question_path': 'name2'}]}}
        merge_case_mappings(diff, form_actions)

        assert action.name_update.question_path == 'name1'
        assert not action.conflicts

    def test_delete_one_of_multiple_conflicts(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name1'},
            'conflicts': [{'question_path': 'name2'}, {'question_path': 'name3'}],
        })
        form_actions = FormActions(open_case=action)

        diff = {'open_case': {'delete': [{'question_path': 'name2'}]}}
        merge_case_mappings(diff, form_actions)

        assert action.name_update
        assert action.conflicts[0].question_path == 'name3'
        assert len(action.conflicts) == 1


class UpdateCaseActionTests(SimpleTestCase):
    def test_construction(self):
        action = UpdateCaseAction({
            'update': {'one': {'question_path': '/root/'}},
            'update_multi': {
                'two': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'},
                ]
            }
        })

        assert action.update['one'].question_path == '/root/'
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        assert multi_paths == {'two': ['/one/', '/two/']}

    def test_make_multi_when_no_updates_does_nothing(self):
        action = UpdateCaseAction({
            'update_multi': {
                'two': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'},
                ]
            }
        })

        changed = action.make_multi()

        assert not changed
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        assert multi_paths == {'two': ['/one/', '/two/']}

    def test_make_multi_when_updates_are_none_does_nothing(self):
        action = UpdateCaseAction({
            'update': None,
            'update_multi': {
                'two': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'},
                ]
            }
        })

        changed = action.make_multi()

        assert not changed
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        assert multi_paths == {'two': ['/one/', '/two/']}

    def test_make_multi_populates_multi(self):
        action = UpdateCaseAction({
            'update': {
                'one': {'question_path': '/one/'},
                'two': {'question_path': '/two/'},
            }
        })

        changed = action.make_multi()

        assert changed
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        assert multi_paths == {'one': ['/one/'], 'two': ['/two/']}
        assert action.update == {}

    def test_normalize_update_when_case_property_has_multiple_questions_does_nothing(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'}
                ]
            }
        })

        applied = action.normalize_update()

        assert not applied
        assert action.update == {}

    def test_normalize_update_moves_update_multi_to_update(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [{'question_path': '/one/'}],
                'two': [{'question_path': '/two/'}]
            }
        })

        applied = action.normalize_update()

        update_paths = {k: v.question_path for (k, v) in action.update.items()}

        assert applied
        assert update_paths == {'one': '/one/', 'two': '/two/'}
        assert action.update_multi == {}

    def test_normalize_update_removes_empty_keys(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': []
            }
        })

        action.normalize_update()

        assert 'one' not in action.update
        assert action.update_multi == {}

    def test_make_single_does_nothing_when_update_multi_is_empty(self):
        action = UpdateCaseAction({
            'update': {
                'one': {'question_path': '/one/'}
            }
        })

        action.make_single()
        assert action.update['one'].question_path == '/one/'
        assert action.update_multi == {}

    def test_make_single_takes_the_last_entry_for_conflicting_case_properties(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [{'question_path': '/one/'}, {'question_path': '/two/'}]
            }
        })

        action.make_single()
        assert action.update['one'].question_path == '/two/'
        assert action.update_multi == {}

    def test_get_property_names_returns_keys_from_update(self):
        action = UpdateCaseAction({
            'update': {
                'one': {'question_path': '/two/'}
            }
        })

        assert action.get_property_names() == {'one'}

    def test_get_property_names_returns_keys_from_update_multi(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [{'question_path': '/two/'}]
            }
        })

        assert action.get_property_names() == {'one'}


class UpdateCaseActionApplyDiffTests(SimpleTestCase):

    def test_no_changes(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'}
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({}, form_actions)

        assert actions.update['one'].question_path == 'one'

    def test_add_value_no_conflict(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'three': [{'question_path': 'some_path'}]},
        }}, form_actions)

        assert set(actions.update.keys()) == {'one', 'two', 'three'}

    def test_add_value_creates_conflict(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question1'}
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': 'question2'}]}
        }}, form_actions)

        assert set(self._conflicting(actions)) == {'one'}
        paths = {c.question_path for c in self._conflicting(actions)['one']}
        assert paths == {'question1', 'question2'}

    def test_add_value_with_legacy_update_multi_conflict(self):
        form_actions = FormActions({'update_case': {'update_multi': {
            'one': [{'question_path': 'question1'}, {'question_path': 'question2'}]
        }}})

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': 'question3'}]}
        }}, form_actions)
        actions = form_actions.update_case

        assert set(actions.conflicts) == {'one'}
        paths = [update.question_path for update in self._conflicting(actions)['one']]
        assert set(paths) == {'question1', 'question2', 'question3'}

    def test_add_value_with_existing_conflict(self):
        actions = UpdateCaseAction({
            'update': {'one': {'question_path': 'question1'}},
            'conflicts': {'one': [{'question_path': 'question2'}]}
        })
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': 'question3'}]}
        }}, form_actions)

        assert set(actions.conflicts) == {'one'}
        paths = [update.question_path for update in self._conflicting(actions)['one']]
        assert set(paths) == {'question1', 'question2', 'question3'}

    def test_adding_duplicate_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question1'}
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': 'question1'}]}
        }}, form_actions)

        assert set(actions.update.keys()) == {'one'}
        assert actions.update['one'].question_path == 'question1'

    def test_adding_existing_modified_property_overwrites_the_property(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one', 'update_mode': 'always'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'add': {'one': [{'question_path': 'one', 'update_mode': 'edit'}]},
        }}, form_actions)

        assert actions.update['one'].update_mode == 'edit'

    def test_remove_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': 'one'}]},
        }}, form_actions)

        assert set(actions.update.keys()) == {'two'}

    def test_deleting_a_missing_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': 'two'}]}
        }}, form_actions)

        assert actions.update.keys() == {'one'}
        assert actions.update['one'].question_path == 'one'

    def test_update_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question_one', 'update_mode': 'always'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'update': {
                'one': [{'question_path': 'question_one', 'update_mode': 'edit'}],
            }
        }}, form_actions)

        assert actions.update['one'].update_mode == 'edit'

    def test_updating_a_missing_property_raises_error(self):
        # If a property was deleted by a different session, updating it shouldn't restore it
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question_one'},
        }})
        form_actions = FormActions(update_case=actions)

        with pytest.raises(MissingPropertyMapException):
            merge_case_mappings({'update_case': {
                'update': {'two': [{'question_path': 'question_two', 'update_mode': 'edit'}]}
            }}, form_actions)

    def test_updating_a_missing_question_raises_error(self):
        # If the specific mapping was deleted by a different session, updating it shouldn't restore it
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'question_one'}
        }})
        form_actions = FormActions(update_case=actions)

        with pytest.raises(MissingPropertyMapException):
            merge_case_mappings({'update_case': {
                'update': {
                    'one': [{'question_path': 'question_two', 'update_mode': 'edit'}]
                }
            }}, form_actions)

    def test_missing_property_exception_contains_all_missing_properties(self):
        actions = UpdateCaseAction({'update': {}})
        form_actions = FormActions(update_case=actions)

        with pytest.raises(MissingPropertyMapException) as context:
            merge_case_mappings({'update_case': {
                'update': {
                    'one': [{'question_path': 'question_one', 'update_mode': 'always'}],
                    'two': [{'question_path': 'question_two', 'update_mode': 'edit'}],
                }
            }}, form_actions)

        assert list(context.value.missing_mappings) == [
            {'case_property': 'one', 'question_path': 'question_one'},
            {'case_property': 'two', 'question_path': 'question_two'}
        ]

    def test_delete_conflict(self):
        actions = UpdateCaseAction({'conflicts': {'one': [{'question_path': 'question_one'}]}})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': 'question_one', 'conflicting_delete': True}]},
        }}, form_actions)

        assert not actions.update
        assert not actions.conflicts

    def test_delete_removes_conflict(self):
        actions = UpdateCaseAction({
            'update': {'one': {'question_path': 'question_one'}},
            'conflicts': {'one': [{'question_path': 'question_two'}]},
        })
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'one': [{'question_path': 'question_one'}]},
        }}, form_actions)

        assert actions.update['one'].question_path == 'question_two'
        assert not actions.conflicts

    def test_multiple_actions_attempting_to_affect_the_same_key_updates_action(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})
        form_actions = FormActions(update_case=actions)

        merge_case_mappings({'update_case': {
            'delete': {'two': [{'question_path': 'two'}]},
            'add': {'two': [{'question_path': 'two', 'update_mode': 'edit'}]},
        }}, form_actions)

        assert actions.update['one'].question_path == 'one'
        assert actions.update['one'].update_mode == 'always'
        assert actions.update['two'].question_path == 'two'
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
        update_case = UpdateCaseAction({'update': {'one': {'question_path': 'two'}}})
        actions = FormActions(update_case=update_case)
        assert actions.all_property_names() == {'one'}

    def test_get_case_mappings_serializes_all_updates(self):
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'name1'},
                'conflicts': [{'question_path': 'name2'}],
            },
            'update_case': {
                'update': {
                    'one': {'question_path': '/A/'},
                    'two': {'question_path': '/C/'},
                },
                'conflicts': {
                    'one': [{'question_path': '/B/'}, {'question_path': '/D/'}],
                }
            },
        })

        json = get_case_mappings(actions)

        assert json == {
            'name': [
                {'question_path': 'name1', 'update_mode': 'always'},
                {'question_path': 'name2', 'update_mode': 'always'},
            ],
            'one': [
                {'question_path': '/A/', 'update_mode': 'always'},
                {'question_path': '/B/', 'update_mode': 'always'},
                {'question_path': '/D/', 'update_mode': 'always'},
            ],
            'two': [{'question_path': '/C/', 'update_mode': 'always'}]
        }

    def test_merge_case_mappings_raises_on_unrecognized_key(self):
        actions = FormActions()
        diff = {'malicious_key': {'update': {}}}

        with pytest.raises(KeyError):
            merge_case_mappings(diff, actions)

    def test_merge_empty_diff(self):
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'name'},
            },
            'update_case': {
                'update': {
                    'one': {'question_path': 'one'},
                    'two': {'question_path': 'two'},
                }
            }
        })
        snapshot = actions.to_json()

        merge_case_mappings({}, actions)

        assert actions['open_case']['name_update']['question_path'] == 'name'
        assert list(actions['update_case']['update'].keys()) == ['one', 'two']
        assert actions.to_json() == snapshot

    def test_merge_case_mappings_with_all_actions_at_once(self):
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'form_name'},
            },
            'update_case': {
                'update': {
                    'one': {'question_path': 'one'},
                    'two': {'question_path': 'two'},
                }
            }
        })

        merge_case_mappings({
            'open_case': {
                'add': [{'question_path': 'new_name'}],
                'delete': [{'question_path': 'form_name'}],
            },
            'update_case': {
                'add': {'three': [{'question_path': 'three'}]},
                'delete': {'one': [{'question_path': 'one'}]},
                'update': {
                    'two': [{'question_path': 'two', 'update_mode': 'edit'}]
                }
            }
        }, actions)

        assert actions.open_case.name_update.question_path == 'new_name'
        assert set(actions.update_case.update.keys()) == {'two', 'three'}
        assert actions.update_case.update['two'].update_mode == 'edit'

    def test_merge_case_mappings_with_double_addition(self):
        # a scenario that would have previously caused DiffConflictException
        # update + add => delete + add + add (last add wins)
        actions = FormActions({
            'open_case': {
                'name_update': {'question_path': 'form_name'},
            },
            'update_case': {
                'update': {
                    'one': {'question_path': 'one'},
                    'two': {'question_path': 'two'},
                }
            }
        })

        merge_case_mappings({
            'open_case': {
                'delete': [{'question_path': 'form_name'}],
                'add': [
                    {'question_path': 'form_name', 'update_mode': 'always'},
                    {'question_path': 'form_name', 'update_mode': 'edit'}
                ],
            },
            'update_case': {
                'delete': {'one': [{'question_path': 'one'}]},
                'add': {'one': [
                    {'question_path': 'one', 'update_mode': 'always'},
                    {'question_path': 'one', 'update_mode': 'edit'},
                ]},
            },
        }, actions)

        assert actions.open_case.name_update.question_path == 'form_name'
        assert actions.open_case.name_update.update_mode == 'edit'
        assert not actions.open_case.conflicts
        assert actions.update_case.update['one'].question_path == 'one'
        assert actions.update_case.update['one'].update_mode == 'edit'
        assert not actions.update_case.conflicts

    def test_update_form_actions_with_conditional_update(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})
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
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})
        form_actions = FormActions(open_case=action)
        actions_json = {'open_case': {'name_update': {'question_path': 'name2'}}}

        update_form_actions(form_actions, actions_json, {})

        assert action.name_update.question_path == 'name'
        assert not action.conflicts

    def test_update_form_actions_ignores_direct_name_update_multi(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})
        form_actions = FormActions(open_case=action)
        actions_json = {'open_case': {'name_update_multi': [{'question_path': 'name2'}]}}

        update_form_actions(form_actions, actions_json, {})

        assert action.name_update.question_path == 'name'
        assert not action.conflicts

    def test_update_form_actions_with_invalid_key_raises_exception(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})
        form_actions = FormActions(open_case=action)
        actions_json = {"open_case": {'invalid_property': {}}}

        with pytest.raises(AttributeError):
            update_form_actions(form_actions, actions_json, {})

    def test_update_form_actions_ignores_direct_updates(self):
        actions = UpdateCaseAction({'update': {'one': {'question_path': 'one'}}})
        form_actions = FormActions(update_case=actions)
        actions_json = {'update_case': {'update': {'one': {'question_path': 'two'}}}}

        update_form_actions(form_actions, actions_json, {})

        assert actions.update['one'].question_path == 'one'
        assert not actions.conflicts

    def test_update_form_actions_ignores_direct_update_multi(self):
        actions = UpdateCaseAction({'update': {'one': {'question_path': 'one'}}})
        form_actions = FormActions(update_case=actions)
        actions_json = {'update_case': {'update_multi': {'one': {'question_path': 'two'}}}}

        update_form_actions(form_actions, actions_json, {})

        assert actions.update['one'].question_path == 'one'
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


class OpenCaseDiffTests(SimpleTestCase):
    def test_construction_with_all_values(self):
        diff = OpenCaseDiff({
            'add': [{'question_path': 'one'}, {'question_path': 'two'}],
            'delete': [{'question_path': 'three'}, {'question_path': 'four'}],
            'update': [{'question_path': 'five', 'update_mode': 'edit'}]
        })

        add_questions = [question.question_path for question in diff.add]
        delete_questions = [question.question_path for question in diff.delete]
        assert add_questions == ['one', 'two']
        assert delete_questions == ['three', 'four']
        assert diff.update[0].update_mode == 'edit'

    def test_convert_to_update_diff(self):
        diff = OpenCaseDiff({
            'add': [{'question_path': 'one'}],
            'delete': [{'question_path': 'two'}],
            'update': [{'question_path': 'three', 'update_mode': 'edit'}]
        })

        update_diff = diff.convert_to_update_diff()

        assert [question.question_path for question in update_diff.add['name_update_multi']] == ['one']
        assert [question.question_path for question in update_diff.delete['name_update_multi']] == ['two']
        assert update_diff.update['name_update_multi'][0].update_mode == 'edit'

    def test_convert_to_update_diff_only_includes_populated_values(self):
        diff = OpenCaseDiff({
            'delete': [{'question_path': 'one'}]
        })

        update_diff = diff.convert_to_update_diff()

        assert [question.question_path for question in update_diff.delete['name_update_multi']] == ['one']
        assert update_diff.add == {}
        assert update_diff.update == {}


class UpdateCaseDiffTests(SimpleTestCase):
    def test_construction_with_all_values(self):
        diff = UpdateCaseDiff({
            'add': {
                'case_one': [{'question_path': 'one'}],
                'case_two': [{'question_path': 'two'}]
            },
            'delete': {
                'case_three': [{'question_path': 'three'}, {'question_path': 'four'}]
            },
            'update': {
                'case_four': [{'question_path': 'five', 'update_mode': 'edit'}]
            }
        })

        assert diff.add['case_one'][0].question_path == 'one'
        assert diff.add['case_two'][0].question_path == 'two'

        assert [question.question_path for question in diff.delete['case_three']] == ['three', 'four']

        assert diff.update['case_four'][0].update_mode == 'edit'


class FormActionsDiffTests(SimpleTestCase):
    def test_json_construction(self):
        diff = FormActionsDiff({
            'open_case': {
                'add': [{'question_path': 'one'}]
            },
            'update_case': {
                'delete': {
                    'case_two': [{'question_path': 'two'}]
                }
            }
        })

        assert diff.open_case.add[0].question_path == 'one'
        assert diff.update_case.delete['case_two'][0].question_path == 'two'

    def test_from_json_creates_diff_object(self):
        universal_json = {
            'add': {
                'prop1': [{'question_path': 'one'}]
            },
            'update': {
                'prop2': [{'question_path': 'two'}]
            },
            'delete': {
                'prop3': [{'question_path': 'three'}]
            }
        }

        diff = FormActionsDiff.from_json(universal_json)

        assert len(diff.update_case.add['prop1']) == 1
        assert diff.update_case.add['prop1'][0].question_path == 'one'

        assert len(diff.update_case.update['prop2']) == 1
        assert diff.update_case.update['prop2'][0].question_path == 'two'

        assert len(diff.update_case.delete['prop3']) == 1
        assert diff.update_case.delete['prop3'][0].question_path == 'three'

    def test_from_json_non_registration_name_stays_in_update(self):
        universal_json = {
            'add': {
                'name': [{'question_path': 'one'}]
            }
        }

        diff = FormActionsDiff.from_json(universal_json)

        assert diff.update_case.add['name'][0].question_path == 'one'
        assert 'name' not in diff.open_case.add

    def test_from_json_registration_name_is_in_open_case(self):
        universal_json = {
            'add': {
                'name': [{'question_path': 'one'}]
            }
        }

        diff = FormActionsDiff.from_json(universal_json, is_registration=True)

        assert diff.open_case.add[0].question_path == 'one'
        assert 'name' not in diff.update_case.add


class ConvertUpdateToAddPlusDeleteTests(SimpleTestCase):

    def test_simple(self):
        diff = {'update': {'one': [{'question_path': '/data/one'}]}}
        snapshot = deepcopy(diff)

        new_diff = _convert_update_to_delete_plus_add(diff)

        assert new_diff == {
            'delete': {'one': [{'question_path': '/data/one'}]},
            'add': {'one': [{'question_path': '/data/one'}]},
        }
        assert diff == snapshot, 'original diff should not be mutated'

    def test_extended(self):
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
                'name': [{'question_path': 'one'}],
                'other': [{'question_path': 'two'}],
            },
            'update': {
                'name': [{'question_path': 'three'}],
                'other': [{'question_path': 'four'}],
            },
            'delete': {
                'name': [{'question_path': 'five'}],
                'other': [{'question_path': 'six'}],
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
                'name': [{'question_path': 'one'}],
                'other': [{'question_path': 'two'}],
            },
            'update': {
                'name': [{'question_path': 'three'}],
                'other': [{'question_path': 'four'}],
            },
            'delete': {
                'name': [{'question_path': 'five'}],
                'other': [{'question_path': 'six'}],
            },
        }
        snapshot = deepcopy(combined_diff)

        diff = from_combined_diff(combined_diff, is_registration=True)

        assert diff['open_case'] == {
            'add': [{'question_path': 'one'}],
            'update': [{'question_path': 'three'}],
            'delete': [{'question_path': 'five'}],
        }
        assert diff['update_case'] == {
            'add': {'other': [{'question_path': 'two'}]},
            'update': {'other': [{'question_path': 'four'}]},
            'delete': {'other': [{'question_path': 'six'}]},
        }
        assert combined_diff == snapshot, 'combined_diff should not be mutated'


class TestMultiTools(SimpleTestCase):

    def test_make_multi(self):
        actions_json = FormActions({
            'open_case': {
                'name_update': {'question_path': 'form_name'},
                'conflicts': [{'question_path': 'other_name'}],
            },
            'update_case': {
                'update': {
                    'one': {'question_path': 'one'},
                    'two': {'question_path': 'two'},
                },
                'conflicts': {
                    'one': [{'question_path': 'other_one'}],
                    'two': [{'question_path': 'other_two'}],
                },
            },
            'usercase_update': {
                'update': {
                    'one': {'question_path': 'test_path'},
                },
            },
        }).to_json()
        snapshot = deepcopy(actions_json)

        multi = make_multi(actions_json)

        assert multi['open_case'] == _Subdict({
            'name_update_multi': [
                _Subdict({'question_path': 'form_name'}),
                _Subdict({'question_path': 'other_name'}),
            ],
        })
        assert multi['update_case'] == _Subdict({
            'update_multi': {
                'one': [
                    _Subdict({'question_path': 'one'}),
                    _Subdict({'question_path': 'other_one'}),
                ],
                'two': [
                    _Subdict({'question_path': 'two'}),
                    _Subdict({'question_path': 'other_two'}),
                ],
            },
        })
        assert 'usercase_update' in multi
        assert multi['usercase_update'].get('update')
        assert actions_json == snapshot, 'actions_json should not be mutated'

    def test_unmake_multi(self):
        input_json = {
            'open_case': {
                'external_id': '0000',
                'name_update_multi': [
                    {'question_path': 'form_name'},
                    {'question_path': 'other_name'},
                ],
                'name_update': {},
                'conflicts': [],
            },
            'update_case': {
                'condition': {'type': 'never'},
                'update_multi': {
                    'one': [{'question_path': 'one'}, {'question_path': 'other_one'}],
                    'two': [{'question_path': 'two'}, {'question_path': 'other_two'}],
                },
                'update': {},
                'conflicts': {},
            },
            'usercase_update': {
                'update': {
                    'one': {'question_path': 'test_path'},
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
                    'one': {'question_path': 'test_path'},
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
            if value != other[key]:
                return False
        return True
