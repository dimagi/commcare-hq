from datetime import datetime
import uuid
from django.conf import settings
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.util import post_case_blocks
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.tests.utils import FormProcessorTestUtils, run_with_all_backends

DOMAIN = 'fundamentals'


class FundamentalCaseTests(TestCase):

    @classmethod
    def setUpClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)

    def setUp(self):
        self.interface = FormProcessorInterface()
        self.casedb = CaseAccessors()

    @run_with_all_backends
    def test_create_case(self):
        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        _submit_case_block(
            True, case_id, user_id='user1', owner_id='owner1', case_type='demo',
            case_name='create_case', date_modified=modified_on, update={
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
            case_name='update_case', date_modified=modified_on, update={
                'dynamic': '1234'
            }
        )

        case = self.casedb.get_case(case_id)
        self.assertEqual(case.owner_id, 'owner2')
        self.assertEqual(case.name, 'update_case')
        self.assertEqual(case.opened_on, opened_on)
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
