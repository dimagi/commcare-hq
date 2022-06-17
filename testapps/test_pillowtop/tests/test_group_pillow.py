import uuid

from django.test import TestCase

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.es import GroupES
from corehq.apps.es.tests.utils import es_test
from corehq.apps.groups.models import Group
from corehq.apps.groups.tests.test_utils import delete_all_groups
from corehq.elastic import get_es_new
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.pillows.mappings.user_mapping import USER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from testapps.test_pillowtop.utils import process_pillow_changes


@es_test
class GroupPillowTest(TestCase):

    def setUp(self):
        self.elasticsearch = get_es_new()
        for index in [GROUP_INDEX_INFO, USER_INDEX_INFO]:
            ensure_index_deleted(index.index)
            initialize_index_and_mapping(self.elasticsearch, index)
        delete_all_groups()
        # setup pillows
        self.process_group_changes = process_pillow_changes('UserGroupsDbKafkaPillow')
        self.process_group_changes.add_pillow('group-pillow')

    def tearDown(self):
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        ensure_index_deleted(USER_INDEX_INFO.index)

    def test_kafka_group_pillow(self):
        domain = uuid.uuid4().hex
        user_id = uuid.uuid4().hex

        # make a group
        with self.process_group_changes:
            group = Group(domain=domain, name='g1', users=[user_id])
            group.save()

        self.elasticsearch.indices.refresh(GROUP_INDEX_INFO.index)

        # verify there
        self._verify_group_in_es(group)

    def test_group_deletion(self):
        domain = uuid.uuid4().hex
        user_id = uuid.uuid4().hex

        with self.process_group_changes:
            group = Group(domain=domain, name='g1', users=[user_id])
            group.save()

        self.elasticsearch.indices.refresh(GROUP_INDEX_INFO.index)
        results = GroupES().run()
        self.assertEqual(1, results.total)

        with self.process_group_changes:
            Group.hard_delete_docs_for_domain(domain)

        self.elasticsearch.indices.refresh(GROUP_INDEX_INFO.index)
        results = GroupES().run()
        self.assertEqual(0, results.total)

    def _verify_group_in_es(self, group):
        results = GroupES().run()
        self.assertEqual(1, results.total)
        es_group = results.hits[0]
        self.assertEqual(group._id, es_group['_id'])
        self.assertEqual(group.name, es_group['name'])
        self.assertEqual(group.users, es_group['users'])
        self.assertEqual('Group', es_group['doc_type'])
