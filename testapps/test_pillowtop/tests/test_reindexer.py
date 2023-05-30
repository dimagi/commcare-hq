import uuid

from django.test import TestCase

from pillowtop.utils import get_pillow_by_name

from corehq.apps.callcenter.tests.test_utils import CallCenterDomainMockTest
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.domain.tests.test_utils import delete_all_domains
from corehq.apps.es import (
    CaseES,
    CaseSearchES,
    DomainES,
    FormES,
    GroupES,
    UserES,
    case_adapter,
    case_search_adapter,
    domain_adapter,
    form_adapter,
    group_adapter,
    user_adapter,
)
from corehq.apps.es.client import manager
from corehq.apps.es.tests.utils import es_test
from corehq.apps.groups.models import Group
from corehq.apps.groups.tests.test_utils import delete_all_groups
from corehq.apps.hqcase.management.commands.ptop_reindexer_v2 import (
    reindex_and_clean,
)
from corehq.apps.users.dbaccessors import delete_all_users
from corehq.apps.users.models import CommCareUser, WebUser
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from corehq.pillows.application import AppReindexerFactory
from corehq.pillows.case import SqlCaseReindexerFactory
from corehq.pillows.domain import DomainReindexerFactory
from corehq.pillows.group import GroupReindexerFactory
from corehq.pillows.groups_to_user import GroupToUserReindexerFactory
from corehq.pillows.sms import SmsReindexerFactory
from corehq.pillows.user import UserReindexerFactory
from corehq.pillows.xform import SqlFormReindexerFactory
from corehq.util.elastic import delete_es_index, ensure_index_deleted
from corehq.util.test_utils import (
    create_and_save_a_case,
    create_and_save_a_form,
    generate_cases,
)
from testapps.test_pillowtop.utils import real_pillow_settings

DOMAIN = 'reindex-test-domain'


@es_test
class PillowtopReindexerTest(TestCase):
    domain = DOMAIN

    def test_domain_reindexer(self):
        delete_all_domains()
        ensure_index_deleted(domain_adapter.index_name)
        name = 'reindex-test-domain'
        create_domain(name)
        reindex_and_clean('domain')
        results = DomainES().run()
        self.assertEqual(1, results.total, results.hits)
        domain_doc = results.hits[0]
        self.assertEqual(name, domain_doc['name'])
        self.assertEqual('Domain', domain_doc['doc_type'])
        self.addCleanup(delete_es_index, domain_adapter.index_name)

    def test_case_reindexer_v2(self):
        FormProcessorTestUtils.delete_all_cases()
        case = _create_and_save_a_case()

        index_id = 'sql-case'
        reindex_and_clean(index_id, reset=True)
        self._assert_case_is_in_es(case)
        self.addCleanup(delete_es_index, case_adapter.index_name)

    def test_case_search_reindexer(self):
        FormProcessorTestUtils.delete_all_cases()
        case = _create_and_save_a_case()
        create_domain(case.domain)

        reindex_and_clean('case-search')
        manager.index_refresh(case_search_adapter.index_name)
        self._assert_case_is_in_es(case, esquery=CaseSearchES())
        self.addCleanup(delete_es_index, case_search_adapter.index_name)

    def test_xform_reindexer_v2(self):
        FormProcessorTestUtils.delete_all_xforms()
        form = create_and_save_a_form(DOMAIN)

        index_id = 'sql-form'
        reindex_and_clean(index_id, reset=True)

        self._assert_form_is_in_es(form)
        self.addCleanup(delete_es_index, form_adapter.index_name)

    def _assert_es_empty(self, esquery=CaseES()):
        results = esquery.run()
        self.assertEqual(0, results.total)

    def _assert_case_is_in_es(self, case, esquery=CaseES()):
        results = esquery.run()
        self.assertEqual(1, results.total)
        case_doc = results.hits[0]
        self.assertEqual(case.case_id, case_doc['_id'])
        self.assertEqual(self.domain, case_doc['domain'])
        self.assertEqual(case.name, case_doc['name'])
        self.assertEqual('CommCareCase', case_doc['doc_type'])

    def _assert_form_is_in_es(self, form):
        results = FormES().run()
        self.assertEqual(1, results.total)
        form_doc = results.hits[0]
        self.assertEqual(self.domain, form_doc['domain'])
        self.assertEqual(form.xmlns, form_doc['xmlns'])
        self.assertEqual('XFormInstance', form_doc['doc_type'])

    def _assert_index_empty(self, esquery=CaseES()):
        results = esquery.run()
        self.assertEqual(0, results.total)


class CheckpointCreationTest(CallCenterDomainMockTest):
    # this class is only here so you can run these explicitly
    pass


@generate_cases([
    (AppReindexerFactory, 'ApplicationToElasticsearchPillow'),
    (DomainReindexerFactory, 'KafkaDomainPillow'),
    (UserReindexerFactory, 'UserPillow'),
    (GroupReindexerFactory, 'GroupPillow'),
    (SmsReindexerFactory, 'SqlSMSPillow'),
], CheckpointCreationTest)
def test_checkpoint_creation(self, reindexer_factory, pillow_name):
    # checks that checkpoipnts are set to the latest checkpoints after reindexing
    with real_pillow_settings():
        pillow = get_pillow_by_name(pillow_name)

        # set the offets to something obviously wrong
        current_offsets = pillow.checkpoint.get_current_sequence_as_dict()
        bad_offsets = {tp: (offset + 38014) for tp, offset in current_offsets.items()}
        pillow.checkpoint.update_to(bad_offsets)
        self.assertNotEqual(current_offsets, pillow.checkpoint.get_current_sequence_as_dict())
        self.assertEqual(bad_offsets, pillow.checkpoint.get_current_sequence_as_dict())

        reindex_and_clean(reindexer_factory.slug)
        pillow = get_pillow_by_name(pillow_name)
        self.assertNotEqual(bad_offsets, pillow.checkpoint.get_current_sequence_as_dict())
        self.assertEqual(
            pillow.get_change_feed().get_latest_offsets_as_checkpoint_value(),
            pillow.checkpoint.get_or_create_wrapped().wrapped_sequence,
        )
        self.assertEqual(
            pillow.get_change_feed().get_latest_offsets_as_checkpoint_value(),
            pillow.checkpoint.get_current_sequence_as_dict(),
        )


@generate_cases([
    (SqlCaseReindexerFactory, 'case-pillow'),
    (SqlFormReindexerFactory, 'xform-pillow'),
    (GroupToUserReindexerFactory, 'UserPillow'),
    (UserReindexerFactory, 'user-pillow'),
    (GroupReindexerFactory, 'group-pillow'),
], CheckpointCreationTest)
@es_test
def test_no_checkpoint_creation(self, reindexer_factory, pillow_name):
    # these pillows should not touch checkpoints since they are run with other
    # reindexers
    with real_pillow_settings():
        pillow = get_pillow_by_name(pillow_name)

        # set these to something obviously wrong
        current_offsets = pillow.checkpoint.get_current_sequence_as_dict()
        bad_offsets = {tp: (offset + 38014) for tp, offset in current_offsets.items()}
        pillow.checkpoint.update_to(bad_offsets)
        self.assertNotEqual(current_offsets, pillow.checkpoint.get_current_sequence_as_dict())
        self.assertEqual(bad_offsets, pillow.checkpoint.get_current_sequence_as_dict())
        reindex_and_clean(reindexer_factory.slug)

        # make sure they are still bad
        pillow = get_pillow_by_name(pillow_name)
        self.assertNotEqual(
            current_offsets,
            pillow.checkpoint.get_current_sequence_as_dict(),
        )
        self.assertEqual(
            bad_offsets,
            pillow.checkpoint.get_current_sequence_as_dict(),
        )
        self.assertNotEqual(
            pillow.get_change_feed().get_latest_offsets_as_checkpoint_value(),
            pillow.checkpoint.get_or_create_wrapped().wrapped_sequence,
        )
        self.assertNotEqual(
            pillow.get_change_feed().get_latest_offsets_as_checkpoint_value(),
            pillow.checkpoint.get_current_sequence_as_dict(),
        )


@es_test(requires=[user_adapter], setup_class=True)
class UserReindexerTest(TestCase):

    def setUp(self):
        super().setUp()
        delete_all_users()

    @classmethod
    def setUpClass(cls):
        super(UserReindexerTest, cls).setUpClass()
        create_domain(DOMAIN)

    def test_user_reindexer_v2(self):
        username = 'reindex-test-username-v2'
        CommCareUser.create(DOMAIN, username, 'secret', None, None)
        reindex_and_clean('user')
        self._assert_user_in_es(username)

    def test_web_user_reindexer_v2(self):
        username = 'test-v2@example.com'
        WebUser.create(DOMAIN, username, 'secret', None, None)
        reindex_and_clean('user')
        self._assert_user_in_es(username, is_webuser=True)

    def _assert_user_in_es(self, username, is_webuser=False):
        results = UserES().run()
        self.assertEqual(1, results.total)
        user_doc = results.hits[0]
        self.assertEqual(username, user_doc['username'])
        if not is_webuser:
            self.assertEqual(DOMAIN, user_doc['domain'])
            self.assertEqual('CommCareUser', user_doc['doc_type'])
        else:
            self.assertEqual('WebUser', user_doc['doc_type'])


@es_test(requires=[group_adapter], setup_class=True)
class GroupReindexerTest(TestCase):

    def setUp(self):
        super(GroupReindexerTest, self).setUp()
        delete_all_groups()

    def test_group_reindexer(self):
        group = Group(domain=DOMAIN, name='g1')
        group.save()
        reindex_and_clean('group')
        self._assert_group_in_es(group)

    def _assert_group_in_es(self, group):
        results = GroupES().run()
        self.assertEqual(1, results.total)
        es_group = results.hits[0]
        self.assertEqual(group._id, es_group['_id'])
        self.assertEqual(group.name, es_group['name'])
        self.assertEqual(group.users, es_group['users'])
        self.assertEqual('Group', es_group['doc_type'])


def _create_and_save_a_case():
    case_name = 'reindexer-test-case-{}'.format(uuid.uuid4().hex)
    case_id = uuid.uuid4().hex
    return create_and_save_a_case(DOMAIN, case_id, case_name)
