import uuid
from django.test import TestCase
from corehq.apps.es import GroupES
from corehq.apps.groups.models import Group
from corehq.dbaccessors.couchapps.all_docs import get_all_docs_with_doc_types
from corehq.elastic import get_es_new
from corehq.pillows.group import GroupPillow
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import unit_testing_only
from pillowtop.es_utils import initialize_index


class GroupPillowTest(TestCase):
    dependent_apps = [
        'corehq.couchapps',
        'corehq.apps.groups'
    ]

    def setUp(self):
        self.elasticsearch = get_es_new()
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        initialize_index(self.elasticsearch, GROUP_INDEX_INFO)
        delete_all_groups()

    def tearDown(self):
        ensure_index_deleted(GROUP_INDEX_INFO.index)

    def test_group_pillow(self):
        domain = uuid.uuid4().hex
        user_id = uuid.uuid4().hex

        # make a group
        group = Group(domain=domain, name='g1', users=[user_id])
        group.save()

        pillow = GroupPillow()
        pillow.use_chunking = False
        pillow.process_changes(since=0, forever=False)
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


@unit_testing_only
def delete_all_groups():
    all_groups = list(get_all_docs_with_doc_types(Group.get_db(), 'Group'))
    Group.bulk_delete(all_groups)
