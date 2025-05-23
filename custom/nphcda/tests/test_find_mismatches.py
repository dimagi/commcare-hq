import doctest
from inspect import cleandoc
from io import StringIO
from unittest.mock import call, patch

from django.test import SimpleTestCase, TestCase

import yaml

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.management.commands.nphcda_find_mismatches import (
    UserChanges,
    UserRow,
    get_commcare_user,
    iter_user_rows,
)

from .contextmanagers import get_temp_filename, get_test_user

DOMAIN = 'test-domain'


class TestIterUserRows(SimpleTestCase):

    def test_iter_user_rows(self):
        csv = cleandoc("""
            State,LGA,Ward,Settlement,Username
            FOO,BAR,BAZ,QUX,FO/BAZ001
            FOO,BAR,BAZ,QUUX,FO/BAZ001
            """)
        with get_temp_filename(csv) as csv_filename:
            user_rows = list(iter_user_rows(csv_filename))
        assert user_rows == [
            UserRow(state='FOO', lga='BAR', ward='BAZ', settlement='QUX', username='FO/BAZ001'),
            UserRow(state='FOO', lga='BAR', ward='BAZ', settlement='QUUX', username='FO/BAZ001'),
        ]

    def test_iter_user_rows_blank_settlement(self):
        csv = cleandoc("""
            State,LGA,Ward,Settlement,Username
            FOO,BAR,BAZ,QUX,FO/BAZ001
            FOO,BAR,BAZ,,FO/BAZ001
            """)
        with get_temp_filename(csv) as csv_filename:
            user_rows = list(iter_user_rows(csv_filename))
        assert user_rows == [
            UserRow(state='FOO', lga='BAR', ward='BAZ', settlement='QUX', username='FO/BAZ001'),
        ]

    def test_iter_user_rows_blank_value(self):
        csv = cleandoc("""
            State,LGA,Ward,Settlement,Username
            FOO,BAR,BAZ,QUX,FO/BAZ001
            FOO,,,QUUX,FO/BAZ001
            """)
        with get_temp_filename(csv) as csv_filename:
            user_rows = list(iter_user_rows(csv_filename))
        assert user_rows == [
            UserRow(state='FOO', lga='BAR', ward='BAZ', settlement='QUX', username='FO/BAZ001'),
            UserRow(state='FOO', lga='BAR', ward='BAZ', settlement='QUUX', username='FO/BAZ001'),
        ]

    def test_iter_user_rows_abbreviated_username(self):
        csv = cleandoc("""
            State,LGA,Ward,Settlement,Username
            FOO,BAR,BAZ,QUX,FO/BAZ001
            FOO,BAR,BAZ,QUUX,BAZ001
            """)
        with get_temp_filename(csv) as csv_filename:
            user_rows = list(iter_user_rows(csv_filename))
        assert user_rows == [
            UserRow(state='FOO', lga='BAR', ward='BAZ', settlement='QUX', username='FO/BAZ001'),
            UserRow(state='FOO', lga='BAR', ward='BAZ', settlement='QUUX', username='FO/BAZ001'),
        ]


class TestGetCommCareUser(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        domain_obj = create_domain(DOMAIN)
        cls.addClassCleanup(domain_obj.delete)

    def test_get_commcare_user(self):
        username = 'fo/baz001@test-domain.commcarehq.org'
        with (
            get_test_user(DOMAIN, username) as user,
            patch('corehq.apps.users.models.CommCareUser.get_by_username') as mock_get_by_username
        ):
            mock_get_by_username.return_value = user

            get_commcare_user('test-domain', 'FO/BAZ001')
            assert mock_get_by_username.mock_calls == [call(username)]

    def test_get_commcare_user_cache_hit(self):
        username = 'fo/baz002@test-domain.commcarehq.org'
        with (
            get_test_user(DOMAIN, username) as user,
            patch('corehq.apps.users.models.CommCareUser.get_by_username') as mock_get_by_username
        ):
            mock_get_by_username.return_value = user

            get_commcare_user('test-domain', 'FO/BAZ002')
            get_commcare_user('test-domain', 'FO/BAZ002')
            assert mock_get_by_username.mock_calls == [call(username)]  # DB hit once

    def test_get_commcare_user_cache_miss(self):
        username1 = 'fo/baz003@test-domain.commcarehq.org'
        username2 = 'fo/baz004@test-domain.commcarehq.org'
        with (
            get_test_user(DOMAIN, username1) as user1,
            get_test_user(DOMAIN, username2) as user2,
            patch('corehq.apps.users.models.CommCareUser.get_by_username') as mock_get_by_username
        ):
            mock_get_by_username.side_effect = [user1, user2]

            get_commcare_user('test-domain', 'FO/BAZ003')
            get_commcare_user('test-domain', 'FO/BAZ004')
            assert mock_get_by_username.mock_calls == [
                call(username1),
                call(username2),
            ]


def test_yaml_output():
    all_user_changes = (uc for uc in [
        UserChanges(
            username='FO/BAZ001',
            location_map={'abc123': 'def456'},
            unmapped_old_locations=[],
            unmapped_new_locations=[],
        ),
        UserChanges(
            username='FO/BAZ002',
            location_map={},
            unmapped_old_locations=['abc123'],
            unmapped_new_locations=[],
        ),
        UserChanges(
            username='FO/BAZ003',
            location_map={},
            unmapped_old_locations=[],
            unmapped_new_locations=['def456'],
        ),
        UserChanges(
            username='FO/BAZ004',
            location_map={'abc123': 'def456'},
            unmapped_old_locations=['abc456'],
            unmapped_new_locations=['def789'],
        ),
    ])
    with StringIO() as f:
        yaml.dump_all(all_user_changes, f)
        f.seek(0)
        output = f.read()
    assert output == cleandoc("""
        location_map:
          abc123: def456
        unmapped_new_locations: []
        unmapped_old_locations: []
        username: FO/BAZ001
        ---
        location_map: {}
        unmapped_new_locations: []
        unmapped_old_locations:
        - abc123
        username: FO/BAZ002
        ---
        location_map: {}
        unmapped_new_locations:
        - def456
        unmapped_old_locations: []
        username: FO/BAZ003
        ---
        location_map:
          abc123: def456
        unmapped_new_locations:
        - def789
        unmapped_old_locations:
        - abc456
        username: FO/BAZ004
        """) + '\n'


def test_doctests():
    import corehq.apps.users.management.commands.nphcda_find_mismatches as module

    results = doctest.testmod(module)
    assert results.failed == 0
