from django.test import SimpleTestCase
from elasticsearch.exceptions import ConnectionError

from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.pillows.user import UserPillow, update_es_user_with_groups
from corehq.util.elastic import ensure_index_deleted
from corehq.util.test_utils import trap_extra_setup


class GroupToUserPillowTest(SimpleTestCase):

    domain = 'grouptouser-pillowtest-domain'

    def setUp(self):
        with trap_extra_setup(ConnectionError):
            ensure_index_deleted(USER_INDEX)
        self.user_pillow = UserPillow()
        self.es_client = get_es_new()
        self.user_id = 'user1'
        self._create_es_user()

    def _create_es_user(self):
        user = CommCareUser(
            _id=self.user_id,
            domain=self.domain,
            username='hc',
            first_name='Harry',
            last_name='Casual',
        )
        self.user_pillow.change_transport(user.to_json())
        self.es_client.indices.refresh(USER_INDEX)
        return user

    def tearDown(self):
        ensure_index_deleted(USER_INDEX)

    def _check_es_user(self, group_ids=None, group_names=None):
        self.es_client.indices.refresh(USER_INDEX)
        es_user = self.es_client.get(USER_INDEX, self.user_id)
        user_doc = es_user['_source']
        if group_ids is None:
            self.assertTrue('__group_ids' not in user_doc)
        else:
            self.assertEqual(set(user_doc['__group_ids']), set(group_ids))

        if group_names is None:
            self.assertTrue('__group_names' not in user_doc)
        else:
            self.assertEqual(set(user_doc['__group_names']), set(group_names))

    def test_update_es_user_with_groups(self):
        group_doc = {
            'name': 'g1',
            '_id': 'group1',
            'users': []
        }

        # no change if user not in group
        update_es_user_with_groups(group_doc)
        self._check_es_user(None, None)

        # user added to group
        group_doc['users'] = [self.user_id]
        update_es_user_with_groups(group_doc)
        self._check_es_user(['group1'], ['g1'])

        # re-process group with no change
        update_es_user_with_groups(group_doc)
        self._check_es_user(['group1'], ['g1'])

        # user added to new group
        new_group = {
            'name': 'g2',
            '_id': 'group2',
            'users': [self.user_id]
        }
        update_es_user_with_groups(new_group)
        self._check_es_user(['group1', 'group2'], ['g1', 'g2'])
