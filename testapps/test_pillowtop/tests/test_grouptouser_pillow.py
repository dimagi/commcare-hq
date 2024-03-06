import uuid
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.producer import producer
from corehq.apps.change_feed.topics import get_topic_offset
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.es.users import user_adapter
from corehq.apps.groups.models import Group
from corehq.apps.groups.tests.test_utils import delete_all_groups
from corehq.apps.hqcase.management.commands.ptop_reindexer_v2 import (
    reindex_and_clean,
)
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.tests.util import patch_user_data_db_layer
from corehq.pillows.groups_to_user import (
    get_group_pillow,
    remove_group_from_users,
    update_es_user_with_groups,
)


@es_test(requires=[user_adapter])
class GroupToUserPillowTest(SimpleTestCase):

    domain = 'grouptouser-pillowtest-domain'

    def setUp(self):
        super(GroupToUserPillowTest, self).setUp()
        self.user_id = 'user1'
        self._create_es_user_without_db_calls(self.user_id, self.domain)

    def _check_es_user(self, group_ids=None, group_names=None):
        _assert_es_user_and_groups(
            self, self.user_id, group_ids, group_names
        )

    def _create_es_user_without_db_calls(self, *args):
        with patch('corehq.apps.groups.dbaccessors.get_group_id_name_map_by_user', return_value=[]):
            _create_es_user(*args)

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

    def test_update_es_user_with_groups_remove_user(self):
        group_doc = {
            'name': 'g1',
            '_id': 'group1',
            'users': [self.user_id],
            'removed_users': set([]),
        }

        # re-process group with no change
        update_es_user_with_groups(group_doc)
        self._check_es_user(['group1'], ['g1'])

        group_doc['removed_users'].add(self.user_id)
        group_doc['users'] = []

        update_es_user_with_groups(group_doc)
        self._check_es_user(None, None)

    def test_remove_user_from_groups_partial_match(self):
        original_id = uuid.uuid4().hex
        group_doc = {
            'name': 'original',
            '_id': original_id,
            'users': [self.user_id]
        }

        # set original groups on the user
        update_es_user_with_groups(group_doc)
        self._check_es_user([original_id], ['original'])

        new_id = uuid.uuid4().hex
        group_doc = {
            'name': 'original',
            '_id': new_id,
            'users': [self.user_id]
        }
        remove_group_from_users(group_doc)


def _assert_es_user_and_groups(test_case, user_id, group_ids=None, group_names=None):
    manager.index_refresh(user_adapter.index_name)
    user_doc = user_adapter.get(user_id)
    if group_ids is None:
        test_case.assertTrue('__group_ids' not in user_doc or not user_doc['__group_ids'])
    else:
        test_case.assertEqual(set(user_doc['__group_ids']), set(group_ids))

    if group_names is None:
        test_case.assertTrue('__group_names' not in user_doc or not user_doc['__group_names'])
    else:
        test_case.assertEqual(set(user_doc['__group_names']), set(group_names))


def _create_es_user(user_id, domain):
    user = CommCareUser(
        _id=user_id,
        domain=domain,
        username='hc',
        first_name='Harry',
        last_name='Casual',
        is_active=True,
    )
    with patch_user_data_db_layer():
        user_adapter.index(user, refresh=True)
    return user


@es_test(requires=[user_adapter])
class GroupToUserPillowDbTest(TestCase):

    def test_pillow(self):
        user_id = uuid.uuid4().hex
        domain = 'dbtest-group-user'
        _create_es_user(user_id, domain)
        _assert_es_user_and_groups(self, user_id, None, None)

        # create and save a group
        group = Group(domain=domain, name='g1', users=[user_id])
        group.save()

        # send to kafka
        since = get_topic_offset(topics.GROUP)
        producer.send_change(topics.GROUP, _group_to_change_meta(group.to_json()))

        # process using pillow
        pillow = get_group_pillow()
        pillow.process_changes(since=since, forever=False)

        # confirm updated in elasticsearch
        manager.index_refresh(user_adapter.index_name)
        _assert_es_user_and_groups(self, user_id, [group._id], [group.name])
        return user_id, group

    def test_pillow_deletion(self):
        user_id, group = self.test_pillow()
        group.soft_delete()

        # send to kafka
        since = get_topic_offset(topics.GROUP)
        producer.send_change(topics.GROUP, _group_to_change_meta(group.to_json()))

        pillow = get_group_pillow()
        pillow.process_changes(since=since, forever=False)

        # confirm removed in elasticsearch
        manager.index_refresh(user_adapter.index_name)
        _assert_es_user_and_groups(self, user_id, [], [])


def _group_to_change_meta(group):
    return change_meta_from_doc(
        document=group,
        data_source_type=data_sources.SOURCE_COUCH,
        data_source_name=Group.get_db().dbname,
    )


@es_test(requires=[user_adapter], setup_class=True)
class GroupsToUserReindexerTest(TestCase):

    def setUp(self):
        super(GroupsToUserReindexerTest, self).setUp()
        delete_all_groups()

    def test_groups_to_user_reindexer(self):
        user_id = uuid.uuid4().hex
        domain = 'test-groups-to-user-reindex'
        _create_es_user(user_id, domain)

        # create and save a group
        group = Group(domain=domain, name='g1', users=[user_id])
        group.save()

        reindex_and_clean('groups-to-user')
        manager.index_refresh(user_adapter.index_name)
        _assert_es_user_and_groups(self, user_id, [group._id], [group.name])
