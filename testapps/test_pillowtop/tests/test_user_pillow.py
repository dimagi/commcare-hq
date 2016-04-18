from django.test import TestCase
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed import document_types
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.producer import producer
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import UserES
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.pillows.user import UserPillow, get_user_kafka_to_elasticsearch_pillow
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index
from testapps.test_pillowtop.utils import get_current_kafka_seq


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

    def test_kafka_user_pillow(self):
        # make a user
        username = 'user-pillow-test-kafka'
        user = CommCareUser.create(TEST_DOMAIN, username, 'secret')

        # send to kafka
        since = get_current_kafka_seq(document_types.COMMCARE_USER)
        producer.send_change(document_types.COMMCARE_USER, _user_to_change_meta(user))

        # send to elasticsearch
        pillow = get_user_kafka_to_elasticsearch_pillow()
        pillow.process_changes(since={document_types.COMMCARE_USER: since}, forever=False)
        self.elasticsearch.indices.refresh(self.index_info.index)
        self._verify_user_in_es(username)

    def _verify_user_in_es(self, username):
        results = UserES().run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(username, user_doc['username'])


def _user_to_change_meta(user):
    user_doc = user.to_json()
    return change_meta_from_doc(
        document=user_doc,
        data_source_type=data_sources.COUCH,
        data_source_name=CommCareUser.get_db().dbname,
    )
