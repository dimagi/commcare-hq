from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import (
    MissingPropertyException,
    DiffConflictException,
    InvalidPropertyException
)
from corehq.apps.app_manager.models import FormActions, UpdateCaseAction


class UpdateCaseActionTests(SimpleTestCase):
    def test_contruction(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        self.assertEqual(list(actions.update.keys()), ['one', 'two'])
        self.assertEqual(actions.update['one']['question_path'], 'one')
        self.assertEqual(actions.update['two']['question_path'], 'two')


class UpdateCaseAction_WithDiffsTests(SimpleTestCase):
    def test_empty_diff(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        result = actions.with_diffs({})

        self.assertEqual(list(result.update.keys()), ['one', 'two'])

    def test_add_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        result = actions.with_diffs({
            'add': {'three': {'question_path': 'some_path'}},
        })

        self.assertEqual(list(result.update.keys()), ['one', 'two', 'three'])

    def test_remove_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        result = actions.with_diffs({
            'del': ['one'],
        })

        self.assertEqual(list(result.update.keys()), ['two'])

    def test_update_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        result = actions.with_diffs({
            'update': {
                'two': {
                    'original': {'question_path': 'two'},
                    'updated': {'question_path': 'four'},
                },
            },
        })

        self.assertEqual(result.update['two'].question_path, 'four')

    def test_updating_stale_value_uses_updated_value(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'changed'}
        }})

        result = actions.with_diffs({
            'update': {
                'two': {
                    'original': {'question_path': 'two'},
                    'updated': {'question_path': 'four'},
                },
            },
        })

        self.assertEqual(result.update['two'].question_path, 'four')

    def test_adding_existing_property_overwrites_the_property(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        result = actions.with_diffs({
            'add': {'one': {'question_path': 'four'}},
        })

        self.assertEqual(result.update['one'].question_path, 'four')

    def test_updating_a_missing_property_raises_error(self):
        # If a property was deleted by a different session, updating it shouldn't restore it
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
        }})

        with self.assertRaises(MissingPropertyException):
            actions.with_diffs({
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
            actions.with_diffs({
                'update': {
                    'one': {
                        'incoming': {'question_path': 'a'},
                        'updated': {'question_path': 'one'},
                    },
                    'two': {
                        'incoming': {'question_path': 'b'},
                        'updated': {'question_path': 'two'}
                    }
                }
            })

        self.assertEqual(set(context.exception.missing_properties), {'one', 'two'})

    def test_deleting_a_missing_property_does_nothing(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
        }})

        result = actions.with_diffs({'del': ['two']})

        self.assertEqual(list(result.update.keys()), ['one'])

    def test_multiple_actions_attempting_to_affect_the_same_key_raises_error(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        with self.assertRaises(DiffConflictException):
            actions.with_diffs({
                'update': {'two': {
                    'original': {'question_path': 'two'},
                    'updated': {'question_path': 'three'}
                }},
                'del': ['two']
            })

    def test_all_actions_at_once(self):
        actions = UpdateCaseAction({'update': {
            'one': {'question_path': 'one'},
            'two': {'question_path': 'two'}
        }})

        result = actions.with_diffs({
            'add': {'three': {'question_path': 'three'}},
            'del': ['one'],
            'update': {'two': {
                'original': {'question_path': 'two'},
                'updated': {'question_path': 'nine'}
            }}
        })

        self.assertEqual(list(result.update.keys()), ['two', 'three'])
        self.assertEqual(result.update['two'].question_path, 'nine')


class FormActionsTests(SimpleTestCase):
    def test_constructor_creates_empty_values(self):
        actions = FormActions()
        self.assertEqual(actions.update_case.update, {})


class FormActions_UpdateTests(SimpleTestCase):
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

        actions.update(updates)

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
            actions.update(updates)

        self.assertEqual(context.exception.invalid_property, 'malicious_key')
