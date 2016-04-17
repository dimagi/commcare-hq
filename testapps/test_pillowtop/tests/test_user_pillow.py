from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import UserES
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.pillows.user import UserPillow
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index


TEST_DOMAIN = 'user-pillow-test'


class UserPillowTest(TestCase):
    dependent_apps = [
        'auditcare', 'django_digest', 'pillowtop',
        'corehq.apps.domain', 'corehq.apps.users', 'corehq.apps.tzmigration',
    ]

    def setUp(self):
        self.index_info = USER_INDEX_INFO
        self.elasticsearch = get_es_new()
        delete_all_users()
        ensure_index_deleted(self.index_info.index)
        initialize_index(self.elasticsearch, self.index_info)

    @classmethod
    def setUpClass(cls):
        create_domain(TEST_DOMAIN)

    def tearDown(self):
        ensure_index_deleted(self.index_info.index)

    def test_user_pillow(self):
        # make a user
        username = 'user-pillow-test-username'
        CommCareUser.create(TEST_DOMAIN, username, 'secret')

        # send to elasticsearch
        pillow = UserPillow()
        pillow.process_changes(since=0, forever=False)
        self.elasticsearch.indices.refresh(self.index_info.index)
        self._verify_user_in_es(username)

    def _verify_user_in_es(self, username):
        results = UserES().run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(username, user_doc['username'])
