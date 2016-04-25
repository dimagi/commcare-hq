import uuid
from django.test import SimpleTestCase, TestCase
from corehq.apps.groups.models import Group

from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new
from corehq.pillows.groups_to_user import update_es_user_with_groups, GroupToUserPillow
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.pillows.user import UserPillow
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping


class GroupToUserPillowTest(SimpleTestCase):

    domain = 'grouptouser-pillowtest-domain'

    def setUp(self):
        ensure_index_deleted(USER_INDEX)
        self.es_client = get_es_new()
        initialize_index_and_mapping(self.es_client, USER_INDEX_INFO)
        self.user_id = 'user1'
        _create_es_user(self.es_client, self.user_id, self.domain)

    def tearDown(self):
        ensure_index_deleted(USER_INDEX)

    def _check_es_user(self, group_ids=None, group_names=None):
        _assert_es_user_and_groups(
            self, self.es_client, self.user_id, group_ids, group_names)

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


def _assert_es_user_and_groups(test_case, es_client, user_id, group_ids=None, group_names=None):
    es_client.indices.refresh(USER_INDEX)
    es_user = es_client.get(USER_INDEX, user_id)
    user_doc = es_user['_source']
    if group_ids is None:
        test_case.assertTrue('__group_ids' not in user_doc)
    else:
        test_case.assertEqual(set(user_doc['__group_ids']), set(group_ids))

    if group_names is None:
        test_case.assertTrue('__group_names' not in user_doc)
    else:
        test_case.assertEqual(set(user_doc['__group_names']), set(group_names))


def _create_es_user(es_client, user_id, domain):
    user = CommCareUser(
        _id=user_id,
        domain=domain,
        username='hc',
        first_name='Harry',
        last_name='Casual',
    )
    UserPillow().change_transport(user.to_json())
    es_client.indices.refresh(USER_INDEX)
    return user


class GroupToUserPillowDbTest(TestCase):
    dependent_apps = ['corehq.apps.groups']

    def setUp(self):
        ensure_index_deleted(USER_INDEX)
        self.es_client = get_es_new()
        initialize_index_and_mapping(self.es_client, USER_INDEX_INFO)

    def tearDown(self):
        ensure_index_deleted(USER_INDEX)

    def test_pillow(self):
        user_id = uuid.uuid4().hex
        domain = 'dbtest-group-user'
        _create_es_user(self.es_client, user_id, domain)
        _assert_es_user_and_groups(self, self.es_client, user_id, None, None)

        # make and save group
        group = Group(domain=domain, name='g1', users=[user_id])
        group.save()

        # process using pillow
        pillow = GroupToUserPillow()
        pillow.use_chunking = False  # hack - make sure the pillow doesn't chunk
        pillow.process_changes(since=0, forever=False)

        # confirm updated in elasticsearch
        self.es_client.indices.refresh(USER_INDEX)
        _assert_es_user_and_groups(self, self.es_client, user_id, [group._id], [group.name])
        return user_id, group

    def test_pillow_deletion(self):
        user_id, group = self.test_pillow()
        group.soft_delete()
        pillow = GroupToUserPillow()
        pillow.use_chunking = False  # hack - make sure the pillow doesn't chunk
        pillow.process_changes(since=0, forever=False)

        # confirm removed in elasticsearch
        self.es_client.indices.refresh(USER_INDEX)
        _assert_es_user_and_groups(self, self.es_client, user_id, [], [])
