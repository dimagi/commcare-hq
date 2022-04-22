from django.test import TestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.models import load_app_template


class TestFormActionsWrap(TestCase):
    """
    This tests that the lazy migration wrap functions being used for the transition of 5 app manager
    models (most notably including the addition of ConditionalCase updateare working properly.
    This test can be deleted after the successful migration of these models.
    """
    def setUp(self):
        self.app = Application.wrap(load_app_template("wash_before_cond_case_update"))

    def test_app_wrapping(self):

        form_actions_A = self.app.modules[0].forms[0].actions
        # OpenCaseAction
        self.assertTrue(hasattr(form_actions_A.open_case, 'name_update'))
        self.assertEqual(form_actions_A.open_case.name_update.question_path, '/data/client_full_name')
        self.assertEqual(form_actions_A.open_case.name_update.update_mode, 'always')
        # UpdateCaseAction
        self.assertTrue('last_reading_date' in form_actions_A.update_case.update)
        self.assertTrue(hasattr(form_actions_A.update_case.update['last_reading_date'], 'question_path'))
        self.assertEqual(form_actions_A.update_case.update['last_reading_date'].question_path,
        '/data/last_reading_date')

        form_actions_B = self.app.modules[1].forms[0].actions
        # OpenSubCaseAction
        self.assertTrue('repairs' in form_actions_B.subcases[0].case_properties)
        self.assertTrue(hasattr(form_actions_B.subcases[0].case_properties['repairs'], 'question_path'))
        self.assertEqual(form_actions_B.subcases[0].case_properties['repairs'].question_path,
        '/data/repairs')
        self.assertTrue(hasattr(form_actions_B.subcases[0], 'name_update'))
        self.assertEqual(form_actions_B.subcases[0].name_update.question_path, '/data/client_name')
