from django.test import SimpleTestCase
from corehq.apps.app_manager.models import UpdateCaseAction


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
