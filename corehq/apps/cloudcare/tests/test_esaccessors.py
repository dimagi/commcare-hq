import uuid
from unittest.mock import MagicMock, patch

from django.test import TestCase

from corehq.apps.cloudcare.esaccessors import login_as_user_query
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.models import CommCareUser


@es_test(requires=[user_adapter])
class TestLoginAsUserQuery(TestCase):

    @classmethod
    def setUpClass(cls):
        super(TestLoginAsUserQuery, cls).setUpClass()
        cls.username = 'superman'
        cls.first_name = 'clark'
        cls.last_name = 'kent'
        cls.doc_type = 'CommCareUser'
        cls.domain = 'user-esaccessors-test'

    def _send_user_to_es(self, _id=None, username=None, user_data=None):
        user = CommCareUser.create(
            domain=self.domain,
            username=username or self.username,
            password='password',
            created_by=None,
            created_via=None,
            _id=_id or uuid.uuid4().hex,
            first_name=self.first_name,
            last_name=self.last_name,
            is_active=True,

        )
        user.save()
        self.addCleanup(user.delete, self.domain, deleted_by=None)
        if user_data:
            user.get_user_data(self.domain).update(user_data)
            user.get_user_data(self.domain).save()

        with patch('corehq.apps.groups.dbaccessors.get_group_id_name_map_by_user', return_value=[]):
            user_adapter.index(user, refresh=True)
        return user

    def test_login_as_user_query_username(self):
        self._send_user_to_es(username='superman')
        self._send_user_to_es(username='superwoman')
        self._send_user_to_es(username='batman')

        self.assertEqual(
            login_as_user_query(
                self.domain,
                MagicMock(),
                'super',
                10,
                0,
            ).count(),
            2,
        )

    def test_login_as_user_query_all(self):
        self._send_user_to_es(username='batman')
        self._send_user_to_es(username='robin')

        self.assertEqual(
            login_as_user_query(
                self.domain,
                MagicMock(),
                None,
                10,
                0,
            ).count(),
            2,
        )

    def test_limited_users(self):
        self._send_user_to_es(username='superman')
        self._send_user_to_es(username='robin', user_data={'login_as_user': 'batman'})

        with patch('corehq.apps.cloudcare.esaccessors._limit_login_as', return_value=True):
            self.assertEqual(
                login_as_user_query(
                    self.domain,
                    MagicMock(username='batman'),
                    None,
                    10,
                    0
                ).count(),
                1
            )

    def test_limited_users_case_insensitive(self):
        with patch('corehq.apps.groups.dbaccessors.get_group_id_name_map_by_user', return_value=[]):
            self._send_user_to_es(username='superman')
            self._send_user_to_es(username='robin', user_data={'login_as_user': 'BATMAN'})

        with patch('corehq.apps.cloudcare.esaccessors._limit_login_as', return_value=True):
            self.assertEqual(
                login_as_user_query(
                    self.domain,
                    MagicMock(username='batman'),
                    None,
                    10,
                    0
                ).values_list("username", flat=True),
                ["robin"]
            )

    def test_limited_users_partial_match(self):
        self._send_user_to_es(username='superman')
        self._send_user_to_es(username='robin', user_data={'login_as_user': 'batman and robin'})

        with patch('corehq.apps.cloudcare.esaccessors._limit_login_as', return_value=True):
            self.assertEqual(
                login_as_user_query(
                    self.domain,
                    MagicMock(username='batman'),
                    None,
                    10,
                    0
                ).values_list("username", flat=True),
                ["robin"]
            )

    def test_default_user(self):
        self._send_user_to_es(username='superman')
        self._send_user_to_es(username='robin', user_data={'login_as_user': 'batman'})
        self._send_user_to_es(username='superwoman', user_data={'login_as_user': 'default'})

        with patch('corehq.apps.cloudcare.esaccessors._limit_login_as', return_value=True):
            self.assertEqual(
                login_as_user_query(
                    self.domain,
                    MagicMock(username='batman'),
                    None,
                    10,
                    0
                ).count(),
                2
            )
