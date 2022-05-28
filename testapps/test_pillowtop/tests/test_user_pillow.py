from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es import UserES
from corehq.apps.es.tests.utils import es_test
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.form_processor.change_publishers import change_meta_from_sql_form
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.form_processor.utils import TestFormMetadata
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.pillows.user import get_user_pillow_old
from corehq.pillows.xform import get_xform_pillow
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import get_form_ready_to_save
from pillowtop.es_utils import initialize_index_and_mapping

from .base import BasePillowTestCase


@es_test
class UserPillowTestBase(BasePillowTestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'user-pillow-test'
        domain_obj = create_domain(cls.domain)
        cls.addClassCleanup(domain_obj.delete)

    def setUp(self):
        super().setUp()
        self.index_info = USER_INDEX_INFO
        self.elasticsearch = get_es_new()
        delete_all_users()
        ensure_index_deleted(self.index_info.index)
        initialize_index_and_mapping(self.elasticsearch, self.index_info)
        self.addCleanup(ensure_index_deleted, self.index_info.index)


@es_test
class UserPillowTest(UserPillowTestBase):

    def setUp(self):
        super().setUp()
        self.user = CommCareUser.create(self.domain, 'test-user', 'secret', None, None)
        self.user_pillow = get_user_pillow_old(skip_ucr=True)
        self.addCleanup(self.user.delete, self.domain, deleted_by=None)

    def test_created_user_sent_to_elasticsearch(self):
        since = get_topic_offset(topics.COMMCARE_USER)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))

        self.user_pillow.process_changes(since=since, forever=False)

        self.elasticsearch.indices.refresh(self.index_info.index)
        hits = UserES().run().hits
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]['username'], 'test-user')

    def test_edited_user_sent_to_elasticsearch(self):
        since = get_topic_offset(topics.COMMCARE_USER)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))
        self.user_pillow.process_changes(since=since, forever=False)
        self.user.first_name = 'edited'
        self.user.save()
        since = get_topic_offset(topics.COMMCARE_USER)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))

        self.user_pillow.process_changes(since=since, forever=False)

        self.elasticsearch.indices.refresh(self.index_info.index)
        user_doc = UserES().run().hits[0]
        self.assertEqual(user_doc['first_name'], 'edited')

    def test_deleted_user_sent_to_elasticsearch(self):
        since = get_topic_offset(topics.COMMCARE_USER)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))
        self.user.retire(self.domain, deleted_by=None)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))

        self.user_pillow.process_changes(since=since, forever=False)

        self.elasticsearch.indices.refresh(self.index_info.index)
        self.assertEqual(0, UserES().run().total)

    def test_multiple_published_changes_sent_to_elasticsearch(self):
        since = get_topic_offset(topics.COMMCARE_USER)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))
        self.user.first_name = 'multiple'
        self.user.save()
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))
        self.user.retire(self.domain, deleted_by=None)
        producer.send_change(topics.COMMCARE_USER, _user_to_change_meta(self.user))

        self.user_pillow.process_changes(since=since, forever=False)

        self.elasticsearch.indices.refresh(self.index_info.index)
        self.assertEqual(0, UserES().run().total)


@es_test
class UnknownUserPillowTest(UserPillowTestBase):

    def test_unknown_user_pillow(self):
        FormProcessorTestUtils.delete_all_xforms()
        user_id = 'test-unknown-user'
        metadata = TestFormMetadata(domain=self.domain, user_id='test-unknown-user')
        form = get_form_ready_to_save(metadata)
        FormProcessorInterface(domain=self.domain).save_processed_models([form])

        # send to kafka
        topic = topics.FORM_SQL
        since = self._get_kafka_seq()
        producer.send_change(topic, change_meta_from_sql_form(form))

        # send to elasticsearch
        pillow = get_xform_pillow()
        pillow.process_changes(since=since, forever=False)
        self.elasticsearch.indices.refresh(self.index_info.index)

        # the default query doesn't include unknown users so should have no results
        self.assertEqual(0, UserES().run().total)
        # clear the default filters which hide unknown users
        user_es = UserES().remove_default_filters()
        results = user_es.run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(self.domain, user_doc['domain'])
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
