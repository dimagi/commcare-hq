from django.test import SimpleTestCase
from corehq.apps.app_manager.exceptions import (
    DiffConflictException,
    MissingPropertyException,
    InvalidPropertyException
)


class InvalidPropertyExceptionTests(SimpleTestCase):
    def test_constructor(self):
        exception = InvalidPropertyException('test_property')
        self.assertEqual(exception.invalid_property, 'test_property')
        self.assertEqual(str(exception), 'Invalid key found: test_property')


class DiffConflictExceptionTests(SimpleTestCase):
    def test_with_specified_conflicts(self):
        exception = DiffConflictException('a', 'b', 'c')
        self.assertEqual(list(exception.conflicting_keys), ['a', 'b', 'c'])
        self.assertEqual(str(exception), 'The following keys were affected by multiple actions: a, b, c')

    def test_with_nothing_specified(self):
        exception = DiffConflictException()
        self.assertEqual(list(exception.conflicting_keys), [])
        self.assertEqual(str(exception), "No conflicting keys specified")


class MissingPropertyExceptionTests(SimpleTestCase):
    def test_with_specified_properties(self):
        exception = MissingPropertyException('a', 'b', 'c')
        self.assertEqual(list(exception.missing_properties), ['a', 'b', 'c'])
        self.assertEqual(str(exception), 'The following properties were not found: a, b, c')

    def test_with_nothing_specified(self):
        exception = MissingPropertyException()
        self.assertEqual(list(exception.missing_properties), [])
        self.assertEqual(str(exception), "No missing properties specified")
