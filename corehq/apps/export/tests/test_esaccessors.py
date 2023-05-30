import uuid

from django.test import SimpleTestCase

from corehq.apps.es.groups import group_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.export.esaccessors import get_groups_user_ids
from corehq.apps.groups.models import Group


@es_test(requires=[group_adapter], setup_class=True)
class TestGroupUserIds(SimpleTestCase):
    domain = 'group-es-domain'

    def _send_group_to_es(self, _id=None, users=None):
        group = Group(
            domain=self.domain,
            name='narcos',
            users=users or [],
            case_sharing=False,
            reporting=True,
            _id=_id or uuid.uuid4().hex,
        )
        group_adapter.index(group, refresh=True)
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
