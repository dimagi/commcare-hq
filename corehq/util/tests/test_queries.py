from django.contrib.auth.models import User
from django.test.testcases import TestCase

from corehq.util.queries import queryset_to_iterator


class TestQuerysetToIterator(TestCase):

    def test_correct_results_are_returned(self):
        query = User.objects.filter(last_name="Tenenbaum")

        results = list(queryset_to_iterator(query, User, limit=10))

        self.assertEqual(
            [u.username for u in results],
            [u.username for u in self.users],
        )

    def test_results_returned_in_one_query_if_limit_is_greater_than_result_size(self):
        query = User.objects.filter(last_name="Tenenbaum")

        with self.assertNumQueries(1):
            # query 1: Users 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
            results = list(queryset_to_iterator(query, User, limit=11))

        self.assertEqual(len(results), 10)

    def test_results_returned_in_two_queries_if_limit_is_equal_to_result_size(self):
        query = User.objects.filter(last_name="Tenenbaum")

        with self.assertNumQueries(2):
            # query 1: Users 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
            # query 2: Check that there are no users past #10
            results = list(queryset_to_iterator(query, User, limit=10))

        self.assertEqual(len(results), 10)

    def test_results_return_in_three_queries_if_limit_is_less_than_or_equal_to_half_of_result_size(self):
        query = User.objects.filter(last_name="Tenenbaum")

        with self.assertNumQueries(3):
            # query 1: Users 1, 2, 3, 4
            # query 2: Users 5, 6, 7, 8
            # query 3: Users 9, 10
            results = list(queryset_to_iterator(query, User, limit=4))

        self.assertEqual(len(results), 10)

    def test_ordered_queryset_raises_assertion_error_when_ignore_ordering_is_false(self):
        query = User.objects.filter(last_name="Tenenbaum").order_by('username')

        with self.assertRaises(AssertionError):
            # ignore_ordering defaults to False
            list(queryset_to_iterator(query, User, limit=4))

    def test_ordered_queryset_does_not_raise_assertion_error_when_ignore_ordering_is_true(self):
        query = User.objects.filter(last_name="Tenenbaum").order_by('username')
        # test succeeds is AssertionError is not raised
        list(queryset_to_iterator(query, User, limit=4, ignore_ordering=True))

    def test_results_ordered_by_pagination_key_when_paginate_by_is_defined(self):
        query = User.objects.filter(last_name="Tenenbaum")

        results = list(queryset_to_iterator(query, User, limit=4, paginate_by={"username": "gt"}))

        self.assertEqual(
            [u.username for u in results],
            ['alice-user4@example.com',
             'alice-user8@example.com',
             'bob-user1@example.com',
             'bob-user5@example.com',
             'bob-user9@example.com',
             'jane-user3@example.com',
             'jane-user7@example.com',
             'john-user10@example.com',
             'john-user2@example.com',
             'john-user6@example.com'])

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        first_names = ['alice', 'bob', 'john', 'jane']
        cls.users = [
            User.objects.create_user(f'{first_names[i % 4]}-user{i}@example.com', last_name="Tenenbaum")
            for i in range(1, 11)
        ]
