import uuid
from django.test import TestCase
from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.es import GroupES
from corehq.apps.groups.models import Group
from corehq.apps.groups.tests.test_utils import delete_all_groups
from corehq.elastic import get_es_new
from corehq.pillows.groups_to_user import get_group_pillow
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index


class GroupPillowTest(TestCase):

    def setUp(self):
        self.elasticsearch = get_es_new()
        for index in [GROUP_INDEX_INFO, USER_INDEX_INFO]:
            ensure_index_deleted(index.index)
            initialize_index(self.elasticsearch, index)
        delete_all_groups()

    def tearDown(self):
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        ensure_index_deleted(USER_INDEX_INFO.index)

    def test_kafka_group_pillow(self):
        domain = uuid.uuid4().hex
        user_id = uuid.uuid4().hex

        # make a group
        group = Group(domain=domain, name='g1', users=[user_id])
        group.save()

        # send to kafka
        since = get_topic_offset(topics.GROUP)
        change_meta = change_meta_from_doc(
            document=group.to_json(),
            data_source_type=data_sources.SOURCE_COUCH,
            data_source_name=Group.get_db().dbname,
        )
        producer.send_change(topics.GROUP, change_meta)

        # send to elasticsearch
        pillow = get_group_pillow()
        pillow.process_changes(since=since, forever=False)
        self.elasticsearch.indices.refresh(GROUP_INDEX_INFO.index)

        # verify there
        self._verify_group_in_es(group)

    def _verify_group_in_es(self, group):
        results = GroupES().run()
        self.assertEqual(1, results.total)
        es_group = results.hits[0]
        self.assertEqual(group._id, es_group['_id'])
        self.assertEqual(group.name, es_group['name'])
        self.assertEqual(group.users, es_group['users'])
        self.assertEqual('Group', es_group['doc_type'])
