import uuid
from mock import MagicMock, patch

from django.test import SimpleTestCase

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.util.elastic import ensure_index_deleted
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.user import transform_user_for_elasticsearch
from corehq.apps.users.models import CommCareUser

from corehq.apps.cloudcare.esaccessors import login_as_user_query


class TestCloudcareESAccessors(SimpleTestCase):

    def setUp(self):
        super(TestCloudcareESAccessors, self).setUp()
        self.username = 'superman'
        self.first_name = 'clark'
        self.last_name = 'kent'
        self.doc_type = 'CommCareUser'
        self.domain = 'user-esaccessors-test'
        self.es = get_es_new()
        initialize_index_and_mapping(self.es, USER_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(USER_INDEX)
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

        with patch('corehq.pillows.user.Group.by_user', return_value=[]):
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
                can_access_all_locations=True,
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
                can_access_all_locations=True,
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
                can_access_all_locations=True,
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
                can_access_all_locations=True,
            ).count(),
            2,
        )
