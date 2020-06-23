import uuid

from django.test import SimpleTestCase

from mock import MagicMock, patch

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.cloudcare.esaccessors import login_as_user_query
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.user import transform_user_for_elasticsearch
from corehq.util.elastic import ensure_index_deleted


class TestCloudcareESAccessors(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        super(TestCloudcareESAccessors, cls).setUpClass()
        cls.username = 'superman'
        cls.first_name = 'clark'
        cls.last_name = 'kent'
        cls.doc_type = 'CommCareUser'
        cls.domain = 'user-esaccessors-test'
        cls.es = get_es_new()

    def setUp(self):
        initialize_index_and_mapping(self.es, USER_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(USER_INDEX)

    @classmethod
    def tearDownClass(cls):
        super(TestCloudcareESAccessors, cls).tearDownClass()

    def _send_user_to_es(self, _id=None, username=None, user_data=None):
        user = CommCareUser(
            domain=self.domain,
            username=username or self.username,
            _id=_id or uuid.uuid4().hex,
            first_name=self.first_name,
            last_name=self.last_name,
            user_data=user_data or {},
            is_active=True,
        )

        with patch('corehq.pillows.user.get_group_id_name_map_by_user', return_value=[]):
            send_to_elasticsearch('users', transform_user_for_elasticsearch(user.to_json()))
        self.es.indices.refresh(USER_INDEX)
        return user

    def test_login_as_user_query_user_data(self):
        self._send_user_to_es(user_data={'wild': 'child', 'wall': 'flower'})
        self._send_user_to_es(user_data={})
        self._send_user_to_es()
        self._send_user_to_es(user_data={'wild': 'wrong'})

        self.assertEqual(
            login_as_user_query(
                self.domain,
                MagicMock(),
                'child',
                10,
                0,
                user_data_fields=['wild'],
            ).count(),
            1
        )

        # Do not fuzzy match
        self.assertEqual(
            login_as_user_query(
                self.domain,
                MagicMock(),
                'chil',
                10,
                0,
                user_data_fields=['wild'],
            ).count(),
            0
        )

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

    def test_login_as_user_query_username_or_user_data(self):
        self._send_user_to_es(username='superman')
        self._send_user_to_es(username='batman', user_data={'wild': 'nope'})
        self._send_user_to_es(username='robin', user_data={'wild': 'super'})
        self._send_user_to_es(username='superwoman', user_data={'wild': 'super'})

        self.assertEqual(
            login_as_user_query(
                self.domain,
                MagicMock(),
                'super',
                10,
                0,
                user_data_fields=['wild'],
            ).count(),
            3,
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
                    0,
                    []
                ).count(),
                1
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
                    0,
                    []
                ).count(),
                2
            )
