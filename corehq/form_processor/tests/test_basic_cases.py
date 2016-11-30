# -*- coding: utf-8 -*-
from datetime import datetime
import uuid
from django.conf import settings
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.tests.util import check_user_has_case
from casexml.apps.case.util import post_case_blocks
from casexml.apps.phone.tests.utils import create_restore_user
from casexml.apps.phone.restore import restore_cache_key
from casexml.apps.phone.const import RESTORE_CACHE_KEY_PREFIX
from corehq.apps.domain.models import Domain
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.apps.users.dbaccessors.all_commcare_users import delete_all_users
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends
from corehq.form_processor.backends.couch.update_strategy import coerce_to_datetime
from dimagi.utils.couch.cache.cache_core import get_redis_default_cache


DOMAIN = 'fundamentals'


class FundamentalCaseTests(TestCase):

    @classmethod
    def setUpClass(cls):
        super(FundamentalCaseTests, cls).setUpClass()
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)
        super(FundamentalCaseTests, cls).tearDownClass()

    def setUp(self):
        super(FundamentalCaseTests, self).setUp()
        self.interface = FormProcessorInterface()
        self.casedb = CaseAccessors()

    @run_with_all_backends
    def test_create_case(self):
        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=modified_on, date_opened=modified_on, update={
                'dynamic': '123'
            }
        )

        case = self.casedb.get_case(case_id)
        self.assertIsNotNone(case)
        self.assertEqual(case.case_id, case_id)
        self.assertEqual(case.owner_id, 'owner1')
        self.assertEqual(case.type, 'demo')
        self.assertEqual(case.name, 'create_case')
        self.assertEqual(case.opened_on, modified_on)
        self.assertEqual(case.opened_by, 'user1')
        self.assertEqual(case.modified_on, modified_on)
        self.assertEqual(case.modified_by, 'user1')
        self.assertTrue(case.server_modified_on > modified_on)
        self.assertFalse(case.closed)
        self.assertIsNone(case.closed_on)

        if settings.TESTS_SHOULD_USE_SQL_BACKEND:
            self.assertIsNone(case.closed_by)
        else:
            self.assertEqual(case.closed_by, '')

        self.assertEqual(case.dynamic_case_properties()['dynamic'], '123')

    @run_with_all_backends
    def test_create_case_unicode_name(self):
        """
        Submit case blocks with unicode names
        """
        # This was failing hard:
        # http://manage.dimagi.com/default.asp?226582#1145687

        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        case_name = u'प्रसव'
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name=case_name, date_modified=modified_on, update={
                'dynamic': '123'
            }
        )
        case = self.casedb.get_case(case_id)
        self.assertEqual(case.name, case_name)

    @run_with_all_backends
    def test_update_case(self):
        case_id = uuid.uuid4().hex
        opened_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=opened_on, update={
                'dynamic': '123'
            }
        )

        modified_on = datetime.utcnow()
        _submit_case_block(
            False, case_id, user_id='user2', owner_id='owner2',
            case_name='update_case', date_modified=modified_on, date_opened=opened_on, update={
                'dynamic': '1234'
            }
        )

        case = self.casedb.get_case(case_id)
        self.assertEqual(case.owner_id, 'owner2')
        self.assertEqual(case.name, 'update_case')
        self.assertEqual(coerce_to_datetime(case.opened_on), coerce_to_datetime(opened_on))
        self.assertEqual(case.opened_by, 'user1')
        self.assertEqual(case.modified_on, modified_on)
        self.assertEqual(case.modified_by, 'user2')
        self.assertTrue(case.server_modified_on > modified_on)
        self.assertFalse(case.closed)
        self.assertIsNone(case.closed_on)
        self.assertEqual(case.dynamic_case_properties()['dynamic'], '1234')

    @run_with_all_backends
    def test_close_case(self):
        # same as update, closed, closed on, closed by
        case_id = uuid.uuid4().hex
        opened_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=opened_on
        )

        modified_on = datetime.utcnow()
        _submit_case_block(
            False, case_id, user_id='user2', date_modified=modified_on, close=True
        )

        case = self.casedb.get_case(case_id)
        self.assertEqual(case.owner_id, 'owner1')
        self.assertEqual(case.modified_on, modified_on)
        self.assertEqual(case.modified_by, 'user2')
        self.assertTrue(case.closed)
        self.assertEqual(case.closed_on, modified_on)
        self.assertEqual(case.closed_by, 'user2')
        self.assertTrue(case.server_modified_on > modified_on)

    @run_with_all_backends
    def test_empty_update(self):
        case_id = uuid.uuid4().hex
        opened_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=opened_on, update={
                'dynamic': '123'
            }
        )

        modified_on = datetime.utcnow()
        _submit_case_block(
            False, case_id, user_id='user2', date_modified=modified_on, update={}
        )

        case = self.casedb.get_case(case_id)
        self.assertEqual(case.dynamic_case_properties(), {'dynamic': '123'})

    @run_with_all_backends
    def test_case_with_index(self):
        # same as update, indexes
        mother_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, mother_case_id, user_id='user1', owner_id='owner1', case_type='mother',
            case_name='mother', date_modified=datetime.utcnow()
        )

        child_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', mother_case_id)
            }
        )

        case = self.casedb.get_case(child_case_id)
        self.assertEqual(len(case.indices), 1)
        index = case.indices[0]
        self.assertEqual(index.identifier, 'mom')
        self.assertEqual(index.referenced_id, mother_case_id)
        self.assertEqual(index.referenced_type, 'mother')
        self.assertEqual(index.relationship, 'child')

    @run_with_all_backends
    def test_update_index(self):
        mother_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, mother_case_id, user_id='user1', owner_id='owner1', case_type='mother',
            case_name='mother', date_modified=datetime.utcnow()
        )

        child_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', mother_case_id)
            }
        )

        case = self.casedb.get_case(child_case_id)
        self.assertEqual(case.indices[0].identifier, 'mom')

        _submit_case_block(
            False, child_case_id, user_id='user1', date_modified=datetime.utcnow(), index={
                'mom': ('other_mother', mother_case_id)
            }
        )
        case = self.casedb.get_case(child_case_id)
        self.assertEqual(case.indices[0].referenced_type, 'other_mother')

    @run_with_all_backends
    def test_delete_index(self):
        mother_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, mother_case_id, user_id='user1', owner_id='owner1', case_type='mother',
            case_name='mother', date_modified=datetime.utcnow()
        )

        child_case_id = uuid.uuid4().hex
        _submit_case_block(
            True, child_case_id, user_id='user1', owner_id='owner1', case_type='child',
            case_name='child', date_modified=datetime.utcnow(), index={
                'mom': ('mother', mother_case_id)
            }
        )

        case = self.casedb.get_case(child_case_id)
        self.assertEqual(len(case.indices), 1)

        _submit_case_block(
            False, child_case_id, user_id='user1', date_modified=datetime.utcnow(), index={
                'mom': ('mother', '')
            }
        )
        case = self.casedb.get_case(child_case_id)
        self.assertEqual(len(case.indices), 0)

    def test_case_with_attachment(self):
        # same as update, attachments
        pass

    @run_with_all_backends
    def test_date_opened_coercion(self):
        delete_all_users()
        self.project = Domain(name='some-domain')
        self.project.save()
        user = create_restore_user(self.project.name)
        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        case = CaseBlock(
            create=True,
            case_id=case_id,
            user_id=user.user_id, owner_id=user.user_id, case_type='demo',
            case_name='create_case', date_modified=modified_on, date_opened=modified_on, update={
                'dynamic': '123'
            }
        )

        post_case_blocks([case.as_xml()], domain='some-domain')
        # update the date_opened to date type to check for value on restore
        case.date_opened = case.date_opened.date()
        check_user_has_case(self, user, case.as_xml())

    @run_with_all_backends
    def test_restore_caches_cleared(self):
        cache = get_redis_default_cache()
        cache_key = restore_cache_key(RESTORE_CACHE_KEY_PREFIX, 'user_id', version="2.0")
        cache.set(cache_key, 'test-thing')
        self.assertEqual(cache.get(cache_key), 'test-thing')
        form = """
            <data xmlns="http://openrosa.org/formdesigner/blah">
                <meta>
                    <userID>{user_id}</userID>
                </meta>
            </data>
        """
        submit_form_locally(form.format(user_id='user_id'), DOMAIN)
        self.assertIsNone(cache.get(cache_key))


def _submit_case_block(create, case_id, **kwargs):
    domain = kwargs.pop('domain', DOMAIN)
    return post_case_blocks(
        [
            CaseBlock(
                create=create,
                case_id=case_id,
                **kwargs
            ).as_xml()
        ], domain=domain
    )
