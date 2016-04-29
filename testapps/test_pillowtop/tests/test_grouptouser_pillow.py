import uuid
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from corehq.apps.change_feed import data_sources
from corehq.apps.change_feed.document_types import change_meta_from_doc, GROUP
from corehq.apps.change_feed.producer import producer
from corehq.apps.groups.models import Group
from corehq.apps.groups.tests import delete_all_groups

from corehq.apps.users.models import CommCareUser
from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.pillows.groups_to_user import update_es_user_with_groups, get_group_to_user_pillow, \
    remove_group_from_users
from corehq.pillows.mappings.user_mapping import USER_INDEX, USER_INDEX_INFO
from corehq.util.elastic import ensure_index_deleted
from pillowtop.es_utils import initialize_index_and_mapping
from testapps.test_pillowtop.utils import get_current_kafka_seq


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
        remove_group_from_users(group_doc, self.es_client)


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
    send_to_elasticsearch('users', user.to_json())
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

        # create and save a group
        group = Group(domain=domain, name='g1', users=[user_id])
        group.save()

        # send to kafka
        since = get_current_kafka_seq(GROUP)
        producer.send_change(GROUP, _group_to_change_meta(group.to_json()))

        # process using pillow
        pillow = get_group_to_user_pillow()
        pillow.process_changes(since=since, forever=False)

        # confirm updated in elasticsearch
        self.es_client.indices.refresh(USER_INDEX)
        _assert_es_user_and_groups(self, self.es_client, user_id, [group._id], [group.name])
        return user_id, group

    def test_pillow_deletion(self):
        user_id, group = self.test_pillow()
        group.soft_delete()

        # send to kafka
        since = get_current_kafka_seq(GROUP)
        producer.send_change(GROUP, _group_to_change_meta(group.to_json()))

        pillow = get_group_to_user_pillow()
        pillow.process_changes(since=since, forever=False)

        # confirm removed in elasticsearch
        self.es_client.indices.refresh(USER_INDEX)
        _assert_es_user_and_groups(self, self.es_client, user_id, [], [])


def _group_to_change_meta(group):
    return change_meta_from_doc(
        document=group,
        data_source_type=data_sources.COUCH,
        data_source_name=Group.get_db().dbname,
    )


class GroupsToUserReindexerTest(TestCase):
    dependent_apps = [
        'pillowtop',
        'corehq.apps.groups',
        'corehq.couchapps',
    ]

    def setUp(self):
        delete_all_groups()

    @classmethod
    def setUpClass(cls):
        cls.es = get_es_new()
        ensure_index_deleted(USER_INDEX)
        initialize_index_and_mapping(cls.es, USER_INDEX_INFO)

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(USER_INDEX)

    def test_groups_to_user_reindexer(self):
        initialize_index_and_mapping(self.es, USER_INDEX_INFO)
        user_id = uuid.uuid4().hex
        domain = 'test-groups-to-user-reindex'
        _create_es_user(self.es, user_id, domain)

        # create and save a group
        group = Group(domain=domain, name='g1', users=[user_id])
        group.save()

        call_command('ptop_reindexer_v2', **{'index': 'groups-to-user', 'noinput': True})
        self.es.indices.refresh(USER_INDEX)
        _assert_es_user_and_groups(self, self.es, user_id, [group._id], [group.name])
