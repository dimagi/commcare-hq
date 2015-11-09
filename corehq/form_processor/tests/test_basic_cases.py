from datetime import datetime
import uuid
from django.test import TestCase
from casexml.apps.case.mock import CaseBlock
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.test_utils import FormProcessorTestUtils, run_with_all_backends

DOMAIN = 'fundamentals'


class FundamentalCaseTests(TestCase):

    @classmethod
    def setUpClass(cls):
        FormProcessorTestUtils.delete_all_cases(DOMAIN)
        FormProcessorTestUtils.delete_all_xforms(DOMAIN)

    def setUp(self):
        self.interface = FormProcessorInterface()

    @run_with_all_backends
    def test_create_case(self):
        case_id = uuid.uuid4().hex
        modified_on = datetime.utcnow()
        FormProcessorInterface().post_case_blocks(
            [
                CaseBlock(
                    create=True,
                    case_id=case_id,
                    user_id='user1',
                    owner_id='owner1',
                    case_type='type_create',
                    case_name='create_case',
                    date_modified=modified_on
                ).as_xml()
            ], domain=DOMAIN
        )

        case = self.interface.case_model.get(case_id)
        self.assertIsNotNone(case)
        self.assertEqual(case.case_id, case_id)
        self.assertEqual(case.owner_id, 'owner1')
        self.assertEqual(case.case_type, 'type_create')
        self.assertEqual(case.case_name, 'create_case')
        self.assertEqual(case.opened_on, modified_on)
        self.assertEqual(case.opened_by, 'user1')
        self.assertEqual(case.modified_on, modified_on)
        self.assertEqual(case.modified_by, 'user1')
        self.assertTrue(case.server_modified_on > modified_on)
        self.assertFalse(case.closed)
        self.assertTrue(case.closed_by is None or case.closed_by == '')
        self.assertIsNone(case.closed_on)

    def test_update_case(self):
        # userid, updated props, modified on, modified by, server modified
        pass

    def test_close_case(self):
        # same as update, closed, closed on, closed by
        pass

    def test_case_with_index(self):
        # same as update, indexes
        pass

    def test_case_with_attachment(self):
        # same as update, attachments
        pass
