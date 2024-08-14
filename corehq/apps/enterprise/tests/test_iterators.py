from django.test import SimpleTestCase

from corehq.apps.enterprise.iterators import raise_after_max_elements


class TestRaiseAfterMaxElements(SimpleTestCase):
    def test_fully_iterating_will_raise_the_default_exception(self):
        it = raise_after_max_elements([1, 2, 3], 2)
        with self.assertRaisesMessage(Exception, 'Too Many Elements'):
            list(it)

    def test_fully_iterating_will_raise_provided_exception(self):
        it = raise_after_max_elements([1, 2, 3], 2, Exception('Test Message'))
        with self.assertRaisesMessage(Exception, 'Test Message'):
            list(it)

    def test_slicing_iterator_can_avoid_error(self):
        it = raise_after_max_elements([1, 2, 3], 3)
        self.assertEqual(list(it), [1, 2, 3])
