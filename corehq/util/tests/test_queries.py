from django.contrib.auth.models import User
from django.test.testcases import TestCase

from corehq.util.queries import queryset_to_iterator


class TestQuerysetToIterator(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.users = [
            User.objects.create_user(f'user{i}@example.com', last_name="Tenenbaum")
            for i in range(1, 11)
        ]

    @classmethod
    def tearDownClass(cls):
        for user in cls.users:
            user.delete()
        super().tearDownClass()

    def test_queryset_to_iterator(self):
        query = User.objects.filter(last_name="Tenenbaum")
        self.assertEqual(query.count(), 10)

        with self.assertNumQueries(4):
            # query 1: Users 1, 2, 3, 4
            # query 2: Users 5, 6, 7, 8
            # query 3: Users 9, 10
            # query 4: Check that there are no users past #10
            all_users = list(queryset_to_iterator(query, User, limit=4))

        self.assertEqual(
            [u.username for u in all_users],
            [u.username for u in self.users],
        )

    def test_ordered_queryset(self):
        query = User.objects.filter(last_name="Tenenbaum").order_by('username')
        with self.assertRaises(AssertionError):
            list(queryset_to_iterator(query, User, limit=4))

    def test_ordered_queryset_ignored(self):
        query = User.objects.filter(last_name="Tenenbaum").order_by('username')
        all_users = list(queryset_to_iterator(query, User, limit=4, ignore_ordering=True))
        self.assertEqual(
            [u.username for u in all_users],
            [u.username for u in self.users],
        )
