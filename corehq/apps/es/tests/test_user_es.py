import uuid

from django.test import TestCase

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import UserES
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.es.testing import sync_users_to_es


@es_test
class TestUserES(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        initialize_index_and_mapping(get_es_new(), USER_INDEX_INFO)
        cls.elasticsearch = get_es_new()
        cls.domain = 'test-user-es'
        cls.domain_obj = create_domain(cls.domain)

    @classmethod
    def tearDownClass(cls):
        delete_all_users()
        cls.domain_obj.delete()
        ensure_index_deleted(USER_INDEX)
        super().tearDownClass()

    def _create_mobile_worker(self, metadata):
        CommCareUser.create(
            domain=self.domain,
            username=uuid.uuid4().hex,
            password="*****",
            created_by=None,
            created_via=None,
            metadata=metadata,
        )

    def test_user_data_query(self):
        with sync_users_to_es():
            self._create_mobile_worker(metadata={'foo': 'bar'})
            self._create_mobile_worker(metadata={'foo': 'baz'})
            self._create_mobile_worker(metadata={'foo': 'womp', 'fu': 'bar'})
        get_es_new().indices.refresh(USER_INDEX)
        self.assertEqual(UserES().metadata('foo', 'bar').count(), 1)
