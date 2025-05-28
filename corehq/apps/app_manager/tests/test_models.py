from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import MissingPropertyException, DiffConflictException
from corehq.apps.app_manager.models import UpdateCaseAction


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
            'update': {'two': {'question_path': 'four'}},
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
                'update': {'two': {'question_path': 'two'}}
            })

    def test_missing_property_exception_contains_all_missing_properties(self):
        actions = UpdateCaseAction({'update': {}})

        with self.assertRaises(MissingPropertyException) as context:
            actions.with_diffs({
                'update': {
                    'one': {'question_path': 'one'},
                    'two': {'question_path': 'two'}
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
                'update': {'two': {'question_path': 'three'}},
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
            'update': {'two': {'question_path': 'nine'}}
        })

        self.assertEqual(list(result.update.keys()), ['two', 'three'])
        self.assertEqual(result.update['two'].question_path, 'nine')
