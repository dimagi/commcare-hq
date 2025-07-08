from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import (
    MissingPropertyException,
    DiffConflictException,
    InvalidPropertyException
)
from corehq.apps.app_manager.models import FormActions, UpdateCaseAction, OpenCaseAction


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
        self.assertEqual(actions.update_case.update, {})

        # Verify that the updated values were applied
        self.assertEqual(set(actions.usercase_update.update.keys()), {'one'})
        self.assertEqual(actions.usercase_update.update['one'].question_path, 'test_path')
        self.assertEqual(actions.usercase_update.update['one'].update_mode, 'edit')

        self.assertEqual(actions.usercase_update.condition['type'], 'always')
        self.assertEqual(actions.usercase_update.condition['question'], 'test_question')
        self.assertEqual(actions.usercase_update.condition['answer'], 'yes')
        self.assertEqual(actions.usercase_update.condition['operator'], 'selected')

    def test_throws_error_on_unrecognized_key(self):
        actions = FormActions()
        updates = {
            'malicious_key': {
                'update': {}
            }
        }

        with self.assertRaises(InvalidPropertyException) as context:
            actions.update_object(updates)

        self.assertEqual(context.exception.invalid_property, 'malicious_key')


class OpenCaseActionTests(SimpleTestCase):
    def test_construction(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        self.assertEqual(action.name_update.question_path, 'name')

    def test_apply_diffs_with_no_changes(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        action.apply_diffs({})

        self.assertEqual(action.name_update.question_path, 'name')

    def test_apply_diffs_name_update(self):
        action = OpenCaseAction({'name_update': {'question_path': 'name'}})

        action.apply_diffs({'updated': {'question_path': 'updated_name'}})

        self.assertEqual(action.name_update.question_path, 'updated_name')

    def test_multiple_name_updates(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })

        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['name1', 'name2'])

    def test_make_multi_populates_multi(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name'}
        })

        action.make_multi()

        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['name'])
        self.assertIsNone(action.name_update)

    def test_normalize_name_update_when_multiple_updates_exist_does_nothing(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name1'}, {'question_path': 'name2'}]
        })

        action.normalize_name_update()

        self.assertIsNone(action.name_update.question_path)
        multi_paths = [update.question_path for update in action.name_update_multi]
        self.assertEqual(multi_paths, ['name1', 'name2'])

    def test_normalize_name_update_moves_name_update_multi_to_name_update(self):
        action = OpenCaseAction({
            'name_update_multi': [{'question_path': 'name'}]
        })

        action.normalize_name_update()

        self.assertEqual(action.name_update.question_path, 'name')
        self.assertEqual(len(action.name_update_multi), 0)


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

        self.assertEqual(action.update['one'].question_path, '/root/')
        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'two': ['/one/', '/two/']})

    def test_make_multi_when_no_updates_does_nothing(self):
        action = UpdateCaseAction({
            'update_multi': {
                'two': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'},
                ]
            }
        })

        action.make_multi()

        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'two': ['/one/', '/two/']})

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

        action.make_multi()

        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'two': ['/one/', '/two/']})

    def test_make_multi_populates_multi(self):
        action = UpdateCaseAction({
            'update': {
                'one': {'question_path': '/one/'},
                'two': {'question_path': '/two/'},
            }
        })

        action.make_multi()

        multi_paths = {k: [action.question_path for action in v] for (k, v) in action.update_multi.items()}
        self.assertEqual(multi_paths, {'one': ['/one/'], 'two': ['/two/']})
        self.assertEqual(action.update, {})

    def test_normalize_update_when_case_property_has_multiple_questions_does_nothing(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [
                    {'question_path': '/one/'},
                    {'question_path': '/two/'}
                ]
            }
        })

        action.normalize_update()

        self.assertEqual(action.update, {})

    def test_normalize_update_moves_update_multi_to_update(self):
        action = UpdateCaseAction({
            'update_multi': {
                'one': [{'question_path': '/one/'}],
                'two': [{'question_path': '/two/'}]
            }
        })

        action.normalize_update()

        update_paths = {k: v.question_path for (k, v) in action.update.items()}

        self.assertEqual(update_paths, {'one': '/one/', 'two': '/two/'})
        self.assertIsNone(action.update_multi)


class UpdateCaseAction_ApplyDiffs_Tests(SimpleTestCase):
    def test_no_changes(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'}
        }})

        actions.apply_diffs({})

        self.assertEqual(actions.update['one'].question_path, 'one')

    def test_add_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        actions.apply_diffs({
            'add': {'three': {'question_path': 'some_path'}},
        })

        self.assertEqual(set(actions.update.keys()), {'one', 'two', 'three'})

    def test_remove_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        actions.apply_diffs({
            'del': ['one'],
        })

        self.assertEqual(set(actions.update.keys()), {'two'})

    def test_update_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        actions.apply_diffs({
            'update': {
                'two': {
                    'original': {'question_path': 'two'},
                    'updated': {'question_path': 'four'},
                }
            }
        })

        self.assertEqual(actions.update['two'].question_path, 'four')

    def test_updating_stale_value_uses_updated_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'updated'},
        }})

        actions.apply_diffs({
            'update': {
                'one': {
                    'original': {'question_path': 'stale'},
                    'updated': {'question_path': 'four'}
                }
            }
        })

        self.assertEqual(actions.update['one'].question_path, 'four')

    def test_adding_existing_property_overwrites_the_property(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        actions.apply_diffs({
            'add': {'one': {'question_path': 'four'}},
        })

        self.assertEqual(actions.update['one'].question_path, 'four')

    def test_updating_a_missing_property_raises_error(self):
        # If a property was deleted by a different session, updating it shouldn't restore it
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
        }})

        with self.assertRaises(MissingPropertyException):
            actions.apply_diffs({
                'update': {
                    'two': {
                        'original': {'question_path': 'a'},
                        'updated': {'question_path': 'two'}
                    }
                }
            })

    def test_missing_property_exception_contains_all_missing_properties(self):
        actions = UpdateCaseAction({'update': {}})

        with self.assertRaises(MissingPropertyException) as context:
            actions.apply_diffs({
                'update': {
                    'one': {
                        'original': {'question_path': 'a'},
                        'updated': {'question_path': 'one'},
                    },
                    'two': {
                        'original': {'question_path': 'b'},
                        'updated': {'question_path': 'two'}
                    }
                }
            })

        self.assertEqual(set(context.exception.missing_properties), {'one', 'two'})

    def test_deleting_a_missing_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
        }})

        actions.apply_diffs({'del': ['two']})

        self.assertEqual(actions.update.keys(), {'one'})

    def test_multiple_actions_attempting_to_affect_the_same_key_raises_error(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'},
        }})

        with self.assertRaises(DiffConflictException):
            actions.apply_diffs({
                'update': {'two': {
                    'original': {'question_path': 'two'},
                    'updated': {'question_path': 'three'}
                }},
                'del': ['two']
            })


class FormActionsTests(SimpleTestCase):
    def test_constructor_creates_empty_values(self):
        actions = FormActions()
        self.assertEqual(actions.update_case.update, {})


class FormActions_WithDiffsTests(SimpleTestCase):
    def test_empty_diff(self):
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

        result = actions.with_diffs({})

        self.assertEqual(result['open_case']['name_update']['question_path'], 'name')
        self.assertEqual(list(result['update_case']['update'].keys()), ['one', 'two'])

    def test_all_actions_at_once(self):
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

        result = actions.with_diffs({
            'open_case': {
                'original': {'question_path': 'form_name'},
                'updated': {'question_path': 'new_name'}
            },
            'update_case': {
                'add': {'three': {'question_path': 'three'}},
                'del': ['one'],
                'update': {
                    'two': {
                        'original': {'question_path': 'two'},
                        'updated': {'question_path': 'nine'}
                    }
                }
            }
        })

        self.assertEqual(result.open_case.name_update.question_path, 'new_name')
        self.assertEqual(set(result.update_case.update.keys()), {'two', 'three'})
        self.assertEqual(result.update_case.update['two'].question_path, 'nine')
