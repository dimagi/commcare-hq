import uuid

from django.test import SimpleTestCase

from pillowtop.es_utils import initialize_index_and_mapping

from corehq.apps.export.esaccessors import get_groups_user_ids
from corehq.apps.groups.models import Group
from corehq.elastic import get_es_instance, send_to_elasticsearch
from corehq.pillows.mappings.group_mapping import GROUP_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted


class TestGroupUserIds(SimpleTestCase):
    domain = 'group-es-domain'

    @classmethod
    def setUpClass(cls):
        super(TestGroupUserIds, cls).setUpClass()
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        cls.es = get_es_instance()
        initialize_index_and_mapping(cls.es, GROUP_INDEX_INFO)
        cls.es.indices.refresh(GROUP_INDEX_INFO.index)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(GROUP_INDEX_INFO.index)
        super(TestGroupUserIds, cls).tearDownClass()

    def _send_group_to_es(self, _id=None, users=None):
        group = Group(
            domain=self.domain,
            name='narcos',
            users=users or [],
            case_sharing=False,
            reporting=True,
            _id=_id or uuid.uuid4().hex,
        )
        send_to_elasticsearch('groups', group.to_json())
        self.es.indices.refresh(GROUP_INDEX_INFO.index)
        return group

    def test_one_group_to_users(self):
        group1 = self._send_group_to_es(users=['billy', 'joel'])

        user_ids = get_groups_user_ids([group1._id])
        self.assertEqual(set(user_ids), set(['billy', 'joel']))

    def test_multiple_groups_to_users(self):
        group1 = self._send_group_to_es(users=['billy', 'joel'])
        group2 = self._send_group_to_es(users=['eric', 'clapton'])

        user_ids = get_groups_user_ids([group1._id, group2._id])
        self.assertEqual(set(user_ids), set(['billy', 'joel', 'eric', 'clapton']))

    def test_one_user_in_group(self):
        group1 = self._send_group_to_es(users=['billy'])

        user_ids = get_groups_user_ids([group1._id])
        self.assertEqual(set(user_ids), set(['billy']))
