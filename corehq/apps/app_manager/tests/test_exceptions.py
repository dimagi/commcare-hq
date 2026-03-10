from django.test import SimpleTestCase
from django.utils import translation
from corehq.apps.translations.tests.utils import custom_translations, CUSTOM_LANGUAGE
from corehq.apps.app_manager.exceptions import MissingPropertyMapException


class MissingPropertyMapExceptionTests(SimpleTestCase):
    def test_with_specified_properties(self):
        exception = MissingPropertyMapException(
            {'case_property': 'one', 'question_path': 'question_one'},
            {'case_property': 'one', 'question_path': 'question_two'},
            {'case_property': 'two', 'question_path': 'question_three'}
        )
        self.assertEqual(list(exception.missing_mappings), [
            {'case_property': 'one', 'question_path': 'question_one'},
            {'case_property': 'one', 'question_path': 'question_two'},
            {'case_property': 'two', 'question_path': 'question_three'}
        ])
        self.assertEqual(str(exception),
                         "The following mappings were not found: "
                         "one->question_one, one->question_two, two->question_three")

    def test_with_nothing_specified(self):
        exception = MissingPropertyMapException()
        self.assertEqual(list(exception.missing_mappings), [])
        self.assertEqual(str(exception), "Missing properties were not found")

    @custom_translations({'The following mappings were not found: {}': 'Translated: {}'})
    def test_translation(self):
        exception = MissingPropertyMapException(
            {'case_property': 'one', 'question_path': 'question_one'},
            {'case_property': 'one', 'question_path': 'question_two'}
        )

        with translation.override(CUSTOM_LANGUAGE):
            assert exception.get_user_message() == 'Translated: one->question_one, one->question_two'
