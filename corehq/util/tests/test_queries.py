from unittest.mock import patch

from django.contrib.auth.models import User
from django.db import connections
from django.db.models import Q
from django.db.utils import InterfaceError, OperationalError
from django.test.testcases import TestCase

from corehq.util import queries
from corehq.util.queries import _lexicographic_greater_than, queryset_to_iterator


def test_lexicographic_greater_than_single_field():
    assert _lexicographic_greater_than(('id',), (5,)) == Q(id__gt=5)


def test_lexicographic_greater_than_multiple_fields():
    assert _lexicographic_greater_than(('a', 'b'), (1, 2)) == Q(a__gt=1) | Q(a=1, b__gt=2)
    assert (
        _lexicographic_greater_than(('a', 'b', 'c'), (1, 2, 3))
        == Q(a__gt=1) | Q(a=1, b__gt=2) | Q(a=1, b=2, c__gt=3)
    )


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

    def test_pagination_key_multiple_fields(self):
        query = User.objects.filter(last_name="Tenenbaum")

        # All users share a last_name, so paging hinges on the pk tie-breaker
        with self.assertNumQueries(4):
            all_users = list(
                queryset_to_iterator(query, User, limit=4, pagination_key=('last_name', 'pk'))
            )

        self.assertEqual(
            [u.username for u in all_users],
            [u.username for u in self.users],
        )

    def test_seek_key_builds_the_cursor_not_the_sort_key(self):
        # pk and id are the same column on User, so this divergent
        # (sort_key, seek_key) still pages correctly -- and lets us confirm the
        # cursor is built from the seek key ('id'), not the sort key ('pk')
        query = User.objects.filter(last_name="Tenenbaum")
        with patch.object(queries, '_lexicographic_greater_than',
                          wraps=queries._lexicographic_greater_than) as build_cursor:
            all_users = list(
                queryset_to_iterator(query, User, limit=4, pagination_key=(('pk', 'id'),))
            )

        self.assertEqual(
            [u.username for u in all_users],
            [u.username for u in self.users],
        )
        assert build_cursor.call_args_list  # paged past the first chunk
        assert all(call.args[0] == ('id',) for call in build_cursor.call_args_list)

    def test_pagination_key_pk_first(self):
        query = User.objects.filter(last_name="Tenenbaum")

        with self.assertNumQueries(4):
            all_users = list(
                queryset_to_iterator(query, User, limit=4, pagination_key=('pk', 'username'))
            )

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

    def test_retries_chunk_fetch_on_operational_error(self):
        query = User.objects.filter(last_name="Tenenbaum")
        real_fetch = queries._fetch_chunk
        calls = []

        def flaky_fetch(queryset, limit):
            calls.append(1)
            if len(calls) == 1:
                raise OperationalError("simulated pgbouncer disconnect")
            return real_fetch(queryset, limit)

        with patch.object(queries, '_fetch_chunk', side_effect=flaky_fetch), \
                patch.object(queries.time, 'sleep') as mock_sleep, \
                patch.object(connections['default'], 'close') as mock_close:
            result = list(queryset_to_iterator(query, User, limit=4))

        assert len(result) == 10
        assert len(calls) >= 2  # at least one retry happened
        mock_close.assert_called()
        mock_sleep.assert_called_with(1)  # first backoff

    def test_retries_resume_from_last_doc_pk_without_duplicates(self):
        query = User.objects.filter(last_name="Tenenbaum")
        real_fetch = queries._fetch_chunk
        calls = []

        def flaky_fetch(queryset, limit):
            calls.append(1)
            # Fail on the 2nd chunk fetch, succeed on retry
            if len(calls) == 2:
                raise OperationalError("disconnect mid-iteration")
            return real_fetch(queryset, limit)

        with patch.object(queries, '_fetch_chunk', side_effect=flaky_fetch), \
                patch.object(queries.time, 'sleep'), \
                patch.object(connections['default'], 'close'):
            result = list(queryset_to_iterator(query, User, limit=4))

        assert [u.username for u in result] == [u.username for u in self.users]

    def test_gives_up_after_max_attempts(self):
        query = User.objects.filter(last_name="Tenenbaum")

        def always_fail(queryset, limit):
            raise OperationalError("permanent failure")

        with patch.object(queries, '_fetch_chunk', side_effect=always_fail), \
                patch.object(queries.time, 'sleep') as mock_sleep, \
                patch.object(connections['default'], 'close') as mock_close, \
                self.assertRaises(OperationalError):
            list(queryset_to_iterator(query, User, limit=4))

        # One sleep + one close between each pair of attempts, none after the last.
        assert mock_sleep.call_count == len(queries._CHUNK_RETRY_DELAYS)
        assert mock_close.call_count == len(queries._CHUNK_RETRY_DELAYS)
        # And the full backoff schedule was walked in order.
        actual_delays = [call.args[0] for call in mock_sleep.call_args_list]
        assert actual_delays == list(queries._CHUNK_RETRY_DELAYS)

    def test_retries_on_interface_error(self):
        query = User.objects.filter(last_name="Tenenbaum")
        real_fetch = queries._fetch_chunk
        calls = []

        def flaky_fetch(queryset, limit):
            calls.append(1)
            if len(calls) == 1:
                raise InterfaceError("connection already closed")
            return real_fetch(queryset, limit)

        with patch.object(queries, '_fetch_chunk', side_effect=flaky_fetch), \
                patch.object(queries.time, 'sleep'), \
                patch.object(connections['default'], 'close'):
            result = list(queryset_to_iterator(query, User, limit=4))

        assert len(result) == 10
