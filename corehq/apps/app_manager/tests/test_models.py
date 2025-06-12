from django.test import SimpleTestCase
from corehq.apps.app_manager.models import UpdateCaseAction, OpenCaseAction


class OpenCaseActionTests(SimpleTestCase):
    def test_construction(self):
        action = OpenCaseAction({
            'name_update': {'question_path': 'name'}
        })

        self.assertEqual(action.name_update.question_path, 'name')

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
