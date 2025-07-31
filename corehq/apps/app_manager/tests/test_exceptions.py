from django.test import SimpleTestCase
from django.utils import translation
from corehq.apps.translations.tests.utils import custom_translations, CUSTOM_LANGUAGE
from corehq.apps.app_manager.exceptions import (
    DiffConflictException,
    MissingPropertyMapException,
    InvalidPropertyException
)


class InvalidPropertyExceptionTests(SimpleTestCase):
    def test_constructor(self):
        exception = InvalidPropertyException('test_property')
        self.assertEqual(exception.invalid_property, 'test_property')
        self.assertEqual(str(exception), 'Invalid key found: test_property')

    @custom_translations({'Invalid key found: {}': 'Translated: {}'})
    def test_translation(self):
        exception = InvalidPropertyException('test_property')

        with translation.override(CUSTOM_LANGUAGE):
            assert exception.get_user_message() == 'Translated: test_property'


class DiffConflictExceptionTests(SimpleTestCase):
    def test_with_specified_conflicts(self):
        exception = DiffConflictException('a', 'b', 'c')
        self.assertEqual(list(exception.conflicting_mappings), ['a', 'b', 'c'])
        self.assertEqual(str(exception), 'The following mappings were affected by multiple actions: a, b, c')

    def test_with_nothing_specified(self):
        exception = DiffConflictException()
        self.assertEqual(list(exception.conflicting_mappings), [])
        self.assertEqual(str(exception), "No conflicting mappings specified")

    @custom_translations({'The following mappings were affected by multiple actions: {}': 'Translated: {}'})
    def test_translation(self):
        exception = DiffConflictException('a', 'b', 'c')

        with translation.override(CUSTOM_LANGUAGE):
            assert exception.get_user_message() == 'Translated: a, b, c'


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
