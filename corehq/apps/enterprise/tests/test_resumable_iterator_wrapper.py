from django.test import SimpleTestCase
from corehq.apps.enterprise.resumable_iterator_wrapper import ResumableIteratorWrapper


class ResumableIteratorWrapperTests(SimpleTestCase):
    def test_can_iterate_through_a_wrapped_iterator(self):
        initial_it = iter(range(5))
        it = ResumableIteratorWrapper(lambda _: initial_it)
        self.assertEqual(list(it), [0, 1, 2, 3, 4])

    def test_can_iterate_through_a_sequence(self):
        sequence = [0, 1, 2, 3, 4]
        it = ResumableIteratorWrapper(lambda _: sequence)
        self.assertEqual(list(it), [0, 1, 2, 3, 4])

    def test_can_limit_a_sequence(self):
        sequence = [0, 1, 2, 3, 4]
        it = ResumableIteratorWrapper(lambda _: sequence, limit=4)
        self.assertEqual(list(it), [0, 1, 2, 3])

    def test_when_limit_is_less_than_sequence_length_is_incomplete(self):
        sequence = [0, 1, 2, 3, 4]
        it = ResumableIteratorWrapper(lambda _: sequence, limit=4)
        list(it)
        self.assertFalse(it.is_complete)

    def test_when_limit_matches_sequence_size_iterator_is_complete(self):
        sequence = [0, 1, 2, 3, 4]
        it = ResumableIteratorWrapper(lambda _: sequence, limit=5)
        list(it)
        self.assertTrue(it.is_complete)

    def test_get_next_query_params_returns_empty_object_prior_to_iteration(self):
        seq = [
            {'key': 'one', 'val': 'val1'},
            {'key': 'two', 'val': 'val2'},
        ]
        it = ResumableIteratorWrapper(lambda _: seq)
        self.assertEqual(it.get_next_query_params(), {})

    def test_default_get_next_query_params_returns_identity_object(self):
        seq = [
            {'key': 'one', 'val': 'val1'},
            {'key': 'two', 'val': 'val2'},
        ]
        it = ResumableIteratorWrapper(lambda _: seq, )
        next(it)
        self.assertEqual(it.get_next_query_params(), {'value': {'key': 'one', 'val': 'val1'}})

    def test_custom_get_next_query_params_fn(self):
        seq = [
            {'key': 'one', 'val': 'val1'},
            {'key': 'two', 'val': 'val2'},
        ]

        def custom_element_properties_fn(ele):
            return (ele['key'], ele['val'])

        it = ResumableIteratorWrapper(lambda _: seq, custom_element_properties_fn)
        next(it)
        self.assertEqual(it.get_next_query_params(), ('one', 'val1'))

    def test_get_next_query_params_returns_none_when_fully_iterated(self):
        it = ResumableIteratorWrapper(lambda _: range(5))
        list(it)
        self.assertIsNone(it.get_next_query_params())
