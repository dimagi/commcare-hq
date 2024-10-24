from django.test import SimpleTestCase
from corehq.apps.enterprise.resumable_iterator_wrapper import ResumableIteratorWrapper


class ResumableIteratorWrapperTests(SimpleTestCase):
    def test_can_iterate_through_a_wrapped_iterator(self):
        initial_it = iter(range(5))
        it = ResumableIteratorWrapper(initial_it)
        self.assertEqual(list(it), [0, 1, 2, 3, 4])

    def test_can_iterate_through_a_sequence(self):
        sequence = [0, 1, 2, 3, 4]
        it = ResumableIteratorWrapper(sequence)
        self.assertEqual(list(it), [0, 1, 2, 3, 4])

    def test_get_next_query_params_returns_empty_object_prior_to_iteration(self):
        seq = [
            {'key': 'one', 'val': 'val1'},
            {'key': 'two', 'val': 'val2'},
        ]
        it = ResumableIteratorWrapper(seq, )
        self.assertEqual(it.get_next_query_params(), {})

    def test_default_get_next_query_params_returns_identity_object(self):
        seq = [
            {'key': 'one', 'val': 'val1'},
            {'key': 'two', 'val': 'val2'},
        ]
        it = ResumableIteratorWrapper(seq, )
        next(it)
        self.assertEqual(it.get_next_query_params(), {'value': {'key': 'one', 'val': 'val1'}})

    def test_custom_get_next_query_params_fn(self):
        seq = [
            {'key': 'one', 'val': 'val1'},
            {'key': 'two', 'val': 'val2'},
        ]

        def custom_element_properties_fn(ele):
            return (ele['key'], ele['val'])

        it = ResumableIteratorWrapper(seq, custom_element_properties_fn)
        next(it)
        self.assertEqual(it.get_next_query_params(), ('one', 'val1'))

    def test_get_next_query_params_returns_none_when_fully_iterated(self):
        it = ResumableIteratorWrapper(range(5))
        list(it)
        self.assertIsNone(it.get_next_query_params())
