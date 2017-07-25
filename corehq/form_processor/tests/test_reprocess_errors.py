from __future__ import absolute_import, print_function, unicode_literals

import uuid

from django.db.utils import InternalError
from django.test import TestCase
from django.test import override_settings
from mock import patch

from casexml.apps.case.exceptions import InvalidCaseIndex
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.mock import CaseStructure
from casexml.apps.case.util import post_case_blocks
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL, FormAccessorSQL, LedgerAccessorSQL
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.models import XFormInstanceSQL, CaseTransaction
from corehq.form_processor.reprocess import reprocess_xform_error, reprocess_unfinished_stub
from corehq.form_processor.tests.utils import FormProcessorTestUtils
from couchforms.models import UnfinishedSubmissionStub


class ReprocessXFormErrorsTest(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ReprocessXFormErrorsTest, cls).setUpClass()

        cls.domain = uuid.uuid4().hex

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(cls.domain)
        super(ReprocessXFormErrorsTest, cls).tearDownClass()

    def test_reprocess_xform_error(self):
        case_id = uuid.uuid4().hex
        parent_case_id = uuid.uuid4().hex
        case = CaseBlock(
            create=True,
            case_id=case_id,
            user_id='user1',
            owner_id='user1',
            case_type='demo',
            case_name='child',
            index={'parent': ('parent_type', parent_case_id)}
        )

        post_case_blocks([case.as_xml()], domain=self.domain)

        form_accessors = FormAccessors(self.domain)
        error_forms = form_accessors.get_forms_by_type('XFormError', 10)
        self.assertEqual(1, len(error_forms))

        form = error_forms[0]
        with self.assertRaises(InvalidCaseIndex):
            reprocess_xform_error(form)

        case = CaseBlock(
            create=True,
            case_id=parent_case_id,
            user_id='user1',
            owner_id='user1',
            case_type='parent_type',
            case_name='parent',
        )

        post_case_blocks([case.as_xml()], domain=self.domain)

        reprocess_xform_error(form_accessors.get_form(form.form_id))

        form = form_accessors.get_form(form.form_id)
        # self.assertTrue(form.initial_processing_complete)  Can't change this with SQL forms at the moment
        self.assertTrue(form.is_normal)
        self.assertIsNone(form.problem)

        case = CaseAccessors(self.domain).get_case(case_id)
        self.assertEqual(1, len(case.indices))
        self.assertEqual(case.indices[0].referenced_id, parent_case_id)
        self._validate_case(case)

    def _validate_case(self, case):
        self.assertEqual(3, len(case.actions))
        self.assertTrue(case.actions[0].is_case_create)
        self.assertTrue(case.actions[2].is_case_index)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class ReprocessXFormErrorsTestSQL(ReprocessXFormErrorsTest):
    def _validate_case(self, case):
        self.assertEqual(1, len(case.transactions))
        self.assertTrue(case.transactions[0].is_form_transaction)
        self.assertTrue(case.transactions[0].is_case_create)
        self.assertTrue(case.transactions[0].is_case_index)
        self.assertFalse(case.transactions[0].revoked)


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class ReprocessSubmissionStubTests(TestCase):
    def setUp(self):
        super(ReprocessSubmissionStubTests, self).setUp()
        self.domain = uuid.uuid4().hex
        self.factory = CaseFactory(domain=self.domain)
        
    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(ReprocessSubmissionStubTests, self).tearDown()
        
    def test_reprocess_unfinished_submission_case_create(self):
        case_id = uuid.uuid4().hex
        transaction_patch = patch('corehq.form_processor.backends.sql.processor.transaction')
        case_save_patch = patch('corehq.form_processor.backends.sql.dbaccessors.CaseAccessorSQL.save_case',
                                side_effect=InternalError)
        with transaction_patch, case_save_patch, self.assertRaises(InternalError):
            self.factory.create_or_update_cases([
                CaseStructure(case_id=case_id, attrs={'case_type': 'parent', 'create': True})
            ])

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))

        # form that was saved before case error raised
        normal_form_ids = FormAccessorSQL.get_form_ids_in_domain_by_state(self.domain, XFormInstanceSQL.NORMAL)
        self.assertEqual(1, len(normal_form_ids))

        # shows error form (duplicate of form that was saved before case error)
        # this is saved becuase the saving was assumed to be atomic so if there was any error it's assumed
        # the form didn't get saved
        error_forms = FormAccessorSQL.get_forms_by_type(self.domain, 'XFormError', 10)
        self.assertEqual(1, len(error_forms))  # we don't really care about this form in this test
        self.assertEqual(error_forms[0].orig_id, normal_form_ids[0])

        self.assertEqual(0, len(CaseAccessorSQL.get_case_ids_in_domain(self.domain)))

        reprocess_unfinished_stub(stubs[0])
        case_ids = CaseAccessorSQL.get_case_ids_in_domain(self.domain)
        self.assertEqual(1, len(case_ids))
        self.assertEqual(case_id, case_ids[0])

        with self.assertRaises(UnfinishedSubmissionStub.DoesNotExist):
            UnfinishedSubmissionStub.objects.get(pk=stubs[0].pk)

    def test_reprocess_unfinished_submission_case_update(self):
        case_id = uuid.uuid4().hex
        self.factory.create_or_update_cases([
            CaseStructure(case_id=case_id, attrs={'case_type': 'parent', 'create': True})
        ])

        transaction_patch = patch('corehq.form_processor.backends.sql.processor.transaction')
        case_save_patch = patch('corehq.form_processor.backends.sql.dbaccessors.CaseAccessorSQL.save_case',
                                side_effect=InternalError)
        with transaction_patch, case_save_patch, self.assertRaises(InternalError):
            self.factory.create_or_update_cases([
                CaseStructure(case_id=case_id, attrs={'create': False})
            ])

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))

        case = CaseAccessorSQL.get_case(case_id)
        self.assertEqual(1, len(case.transactions))

        normal_form_ids = FormAccessorSQL.get_form_ids_in_domain_by_state(self.domain, XFormInstanceSQL.NORMAL)
        self.assertEqual(2, len(normal_form_ids))

        reprocess_unfinished_stub(stubs[0])

        case = CaseAccessorSQL.get_case(case_id)
        self.assertEqual(2, len(case.transactions))

        with self.assertRaises(UnfinishedSubmissionStub.DoesNotExist):
            UnfinishedSubmissionStub.objects.get(pk=stubs[0].pk)

    def test_reprocess_unfinished_submission_ledger_create(self):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        case_id = uuid.uuid4().hex
        self.factory.create_or_update_cases([
            CaseStructure(case_id=case_id, attrs={'case_type': 'parent', 'create': True})
        ])

        transaction_patch = patch('corehq.form_processor.backends.sql.processor.transaction')
        ledger_save_patch = patch('corehq.form_processor.backends.sql.dbaccessors.LedgerAccessorSQL.save_ledger_values',
                                side_effect=InternalError)
        with transaction_patch, ledger_save_patch, self.assertRaises(InternalError):
            submit_case_blocks(
                get_single_balance_block(case_id, 'product1', 100),
                self.domain
                )

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))

        ledgers = LedgerAccessorSQL.get_ledger_values_for_case(case_id)
        self.assertEqual(0, len(ledgers))

        # case transaction got saved
        case = CaseAccessorSQL.get_case(case_id)
        self.assertEqual(2, len(case.transactions))
        self.assertTrue(case.transactions[0].is_case_create)
        self.assertTrue(case.transactions[1].is_ledger_transaction)

        ledger_transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case_id)
        self.assertEqual(0, len(ledger_transactions))

        reprocess_unfinished_stub(stubs[0])

        ledgers = LedgerAccessorSQL.get_ledger_values_for_case(case_id)
        self.assertEqual(1, len(ledgers))

        ledger_transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case_id)
        self.assertEqual(1, len(ledger_transactions))

        # case still only has 2 transactions
        case = CaseAccessorSQL.get_case(case_id)
        self.assertEqual(2, len(case.transactions))

    def test_reprocess_unfinished_submission_ledger_update(self):
        pass
