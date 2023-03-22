from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import UserES
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.form_processor.change_publishers import change_meta_from_sql_form
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.user import get_user_pillow_old
from corehq.pillows.xform import get_xform_pillow
from corehq.util.test_utils import get_form_ready_to_save

from .base import BasePillowTestCase

TEST_DOMAIN = 'user-pillow-test'


@es_test(requires=[user_adapter])
class UserPillowTestBase(BasePillowTestCase):
    def setUp(self):
        super(UserPillowTestBase, self).setUp()
        delete_all_users()

    @classmethod
    def setUpClass(cls):
        super(UserPillowTestBase, cls).setUpClass()
        create_domain(TEST_DOMAIN)


@es_test
class UserPillowTest(UserPillowTestBase):

    def test_kafka_user_pillow(self):
        self._make_and_test_user_kafka_pillow('user-pillow-test-kafka')

    def test_kafka_user_pillow_deletion(self):
        user = self._make_and_test_user_kafka_pillow('test-kafka-user_deletion')
        # soft delete
        user.retire(TEST_DOMAIN, deleted_by=None)

        # send to kafka
        since = get_topic_offset(topics.COMMCARE_USER)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(user))

        # send to elasticsearch
        pillow = get_user_pillow_old(skip_ucr=True)
        pillow.process_changes(since=since, forever=False)
        manager.index_refresh(user_adapter.index_name)
        self.assertEqual(0, UserES().run().total)

    def _make_and_test_user_kafka_pillow(self, username):
        # make a user
        user = CommCareUser.create(TEST_DOMAIN, username, 'secret', None, None)

        # send to kafka
        since = get_topic_offset(topics.COMMCARE_USER)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(user))

        # send to elasticsearch
        pillow = get_user_pillow_old()
        pillow.process_changes(since=since, forever=False)
        manager.index_refresh(user_adapter.index_name)
        self._verify_user_in_es(username)
        return user

    def _verify_user_in_es(self, username):
        results = UserES().run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(username, user_doc['username'])


@es_test
class UnknownUserPillowTest(UserPillowTestBase):

    def test_unknown_user_pillow(self):
        FormProcessorTestUtils.delete_all_xforms()
        user_id = 'test-unknown-user'
        metadata = TestFormMetadata(domain=TEST_DOMAIN, user_id='test-unknown-user')
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=TEST_DOMAIN).save_processed_models([form])

        # send to kafka
        topic = topics.FORM_SQL
        since = self._get_kafka_seq()
        producer.send_change(topic, change_meta_from_sql_form(form))

        # send to elasticsearch
        pillow = get_xform_pillow()
        pillow.process_changes(since=since, forever=False)
        manager.index_refresh(user_adapter.index_name)

        # the default query doesn't include unknown users so should have no results
        self.assertEqual(0, UserES().run().total)
        # clear the default filters which hide unknown users
        user_es = UserES().remove_default_filters()
        results = user_es.run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(TEST_DOMAIN, user_doc['domain'])
        self.assertEqual(user_id, user_doc['_id'])
        self.assertEqual('UnknownUser', user_doc['doc_type'])

    def _get_kafka_seq(self):
        return get_topic_offset(topics.FORM_SQL)


def _user_to_change_meta(user):
    user_doc = user.to_json()
    return change_meta_from_doc(
        document=user_doc,
        data_source_type=data_sources.SOURCE_COUCH,
        data_source_name=CommCareUser.get_db().dbname,
    )
