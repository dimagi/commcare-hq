from __future__ import absolute_import, print_function, unicode_literals

import contextlib
import uuid

from django.db.utils import InternalError
from django.test import TestCase
from mock import patch

from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.mock import CaseFactory
from casexml.apps.case.mock import CaseStructure
from casexml.apps.case.signals import case_post_save
from casexml.apps.case.util import post_case_blocks
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.products.models import SQLProduct
from corehq.apps.receiverwrapper.util import submit_form_locally
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors, LedgerAccessors
from corehq.form_processor.reprocess import reprocess_xform_error, reprocess_unfinished_stub
from corehq.form_processor.tests.utils import FormProcessorTestUtils, use_sql_backend
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.util.test_utils import catch_signal
from couchforms.models import UnfinishedSubmissionStub
from couchforms.signals import successful_form_received


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
        reprocess_xform_error(form)
        error_forms = form_accessors.get_forms_by_type('XFormError', 10)
        self.assertEqual(1, len(error_forms))

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


@use_sql_backend
class ReprocessXFormErrorsTestSQL(ReprocessXFormErrorsTest):
    def _validate_case(self, case):
        self.assertEqual(1, len(case.transactions))
        self.assertTrue(case.transactions[0].is_form_transaction)
        self.assertTrue(case.transactions[0].is_case_create)
        self.assertTrue(case.transactions[0].is_case_index)
        self.assertFalse(case.transactions[0].revoked)


class ReprocessSubmissionStubTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super(ReprocessSubmissionStubTests, cls).setUpClass()
        cls.domain = uuid.uuid4().hex
        cls.product = SQLProduct.objects.create(domain=cls.domain, product_id='product1', name='product1')

    @classmethod
    def tearDownClass(cls):
        cls.product.delete()
        super(ReprocessSubmissionStubTests, cls).tearDownClass()

    def setUp(self):
        super(ReprocessSubmissionStubTests, self).setUp()
        self.factory = CaseFactory(domain=self.domain)
        self.formdb = FormAccessors(self.domain)
        self.casedb = CaseAccessors(self.domain)
        self.ledgerdb = LedgerAccessors(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(ReprocessSubmissionStubTests, self).tearDown()

    def test_reprocess_unfinished_submission_case_create(self):
        case_id = uuid.uuid4().hex
        with _patch_save_to_raise_error(self):
            self.factory.create_or_update_cases([
                CaseStructure(case_id=case_id, attrs={'case_type': 'parent', 'create': True})
            ])

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))

        # form that was saved before case error raised
        normal_form_ids = self.formdb.get_all_form_ids_in_domain('XFormInstance')
        self.assertEqual(0, len(normal_form_ids))

        # shows error form (duplicate of form that was saved before case error)
        # this is saved becuase the saving was assumed to be atomic so if there was any error it's assumed
        # the form didn't get saved
        # we don't really care about this form in this test
        error_forms = self.formdb.get_forms_by_type('XFormError', 10)
        self.assertEqual(1, len(error_forms))
        self.assertIsNone(error_forms[0].orig_id)
        self.assertEqual(error_forms[0].form_id, stubs[0].xform_id)

        self.assertEqual(0, len(self.casedb.get_case_ids_in_domain()))

        result = reprocess_unfinished_stub(stubs[0])
        self.assertEqual(1, len(result.cases))

        case_ids = self.casedb.get_case_ids_in_domain()
        self.assertEqual(1, len(case_ids))
        self.assertEqual(case_id, case_ids[0])

        with self.assertRaises(UnfinishedSubmissionStub.DoesNotExist):
            UnfinishedSubmissionStub.objects.get(pk=stubs[0].pk)

    def test_reprocess_unfinished_submission_case_update(self):
        case_id = uuid.uuid4().hex
        form_ids = []
        form_ids.append(submit_case_blocks(
            CaseBlock(case_id=case_id, create=True, case_type='box').as_string().decode('utf-8'),
            self.domain
        )[0].form_id)

        with _patch_save_to_raise_error(self):
            submit_case_blocks(
                CaseBlock(case_id=case_id, update={'prop': 'a'}).as_string().decode('utf-8'),
                self.domain
            )

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))

        form_ids.append(stubs[0].xform_id)

        # submit second form with case update
        form_ids.append(submit_case_blocks(
            CaseBlock(case_id=case_id, update={'prop': 'b'}).as_string().decode('utf-8'),
            self.domain
        )[0].form_id)

        case = self.casedb.get_case(case_id)
        self.assertEqual(2, len(case.xform_ids))
        self.assertEqual('b', case.get_case_property('prop'))

        result = reprocess_unfinished_stub(stubs[0])
        self.assertEqual(1, len(result.cases))
        self.assertEqual(0, len(result.ledgers))

        case = self.casedb.get_case(case_id)
        self.assertEqual('b', case.get_case_property('prop'))  # should be property value from most recent form
        self.assertEqual(3, len(case.xform_ids))
        self.assertEqual(form_ids, case.xform_ids)

        with self.assertRaises(UnfinishedSubmissionStub.DoesNotExist):
            UnfinishedSubmissionStub.objects.get(pk=stubs[0].pk)

    def test_reprocess_unfinished_submission_ledger_create(self):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        case_id = uuid.uuid4().hex
        self.factory.create_or_update_cases([
            CaseStructure(case_id=case_id, attrs={'case_type': 'parent', 'create': True})
        ])

        with _patch_save_to_raise_error(self):
            submit_case_blocks(
                get_single_balance_block(case_id, 'product1', 100),
                self.domain
            )

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))

        ledgers = self.ledgerdb.get_ledger_values_for_case(case_id)
        self.assertEqual(0, len(ledgers))

        case = self.casedb.get_case(case_id)
        self.assertEqual(1, len(case.xform_ids))

        ledger_transactions = self.ledgerdb.get_ledger_transactions_for_case(case_id)
        self.assertEqual(0, len(ledger_transactions))

        result = reprocess_unfinished_stub(stubs[0])
        self.assertEqual(1, len(result.cases))
        self.assertEqual(1, len(result.ledgers))

        ledgers = self.ledgerdb.get_ledger_values_for_case(case_id)
        self.assertEqual(1, len(ledgers))

        ledger_transactions = self.ledgerdb.get_ledger_transactions_for_case(case_id)
        self.assertEqual(1, len(ledger_transactions))

        # case still only has 2 transactions
        case = self.casedb.get_case(case_id)
        self.assertEqual(2, len(case.xform_ids))
        if should_use_sql_backend(self.domain):
            self.assertTrue(case.actions[1].is_ledger_transaction)

    def test_reprocess_unfinished_submission_ledger_rebuild(self):
        from corehq.apps.commtrack.tests.util import get_single_balance_block
        case_id = uuid.uuid4().hex
        form_ids = []
        form_ids.append(submit_case_blocks(
            [
                CaseBlock(case_id=case_id, create=True, case_type='shop').as_string().decode('utf-8'),
                get_single_balance_block(case_id, 'product1', 100),
            ],
            self.domain
        )[0].form_id)

        with _patch_save_to_raise_error(self):
            submit_case_blocks(
                get_single_balance_block(case_id, 'product1', 50),
                self.domain
            )

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))
        form_ids.append(stubs[0].xform_id)

        # submit another form afterwards
        form_ids.append(submit_case_blocks(
            get_single_balance_block(case_id, 'product1', 25),
            self.domain
        )[0].form_id)

        ledgers = self.ledgerdb.get_ledger_values_for_case(case_id)
        self.assertEqual(1, len(ledgers))
        self.assertEqual(25, ledgers[0].balance)

        ledger_transactions = self.ledgerdb.get_ledger_transactions_for_case(case_id)
        if should_use_sql_backend(self.domain):
            self.assertEqual(2, len(ledger_transactions))
        else:
            # includes extra consumption transaction
            self.assertEqual(3, len(ledger_transactions))

        # should rebuild ledger transactions
        result = reprocess_unfinished_stub(stubs[0])
        self.assertEqual(1, len(result.cases))
        self.assertEqual(1, len(result.ledgers))

        ledgers = self.ledgerdb.get_ledger_values_for_case(case_id)
        self.assertEqual(1, len(ledgers))  # still only 1
        self.assertEqual(25, ledgers[0].balance)

        ledger_transactions = self.ledgerdb.get_ledger_transactions_for_case(case_id)
        if should_use_sql_backend(self.domain):
            self.assertEqual(3, len(ledger_transactions))
            # make sure transactions are in correct order
            self.assertEqual(form_ids, [trans.form_id for trans in ledger_transactions])
            self.assertEqual(100, ledger_transactions[0].updated_balance)
            self.assertEqual(100, ledger_transactions[0].delta)
            self.assertEqual(50, ledger_transactions[1].updated_balance)
            self.assertEqual(-50, ledger_transactions[1].delta)
            self.assertEqual(25, ledger_transactions[2].updated_balance)
            self.assertEqual(-25, ledger_transactions[2].delta)

        else:
            self.assertEqual(3, len(ledger_transactions))
            self.assertEqual(form_ids, [trans.report.form_id for trans in ledger_transactions])
            self.assertEqual(100, ledger_transactions[0].stock_on_hand)
            self.assertEqual(50, ledger_transactions[1].stock_on_hand)
            self.assertEqual(25, ledger_transactions[2].stock_on_hand)

    def test_fire_signals(self):
        from corehq.apps.receiverwrapper.tests.test_submit_errors import failing_signal_handler
        case_id = uuid.uuid4().hex
        form_id = uuid.uuid4().hex
        with failing_signal_handler('signal death'):
            submit_case_blocks(
                CaseBlock(case_id=case_id, create=True, case_type='box').as_string().decode('utf-8'),
                self.domain,
                form_id=form_id
            )

        form = self.formdb.get_form(form_id)

        with catch_signal(successful_form_received) as form_handler, catch_signal(case_post_save) as case_handler:
            submit_form_locally(
                instance=form.get_xml(),
                domain=self.domain,
            )

        case = self.casedb.get_case(case_id)

        if should_use_sql_backend(self.domain):
            self.assertEqual(form, form_handler.call_args[1]['xform'])
            self.assertEqual(case, case_handler.call_args[1]['case'])
        else:
            signal_form = form_handler.call_args[1]['xform']
            self.assertEqual(form.form_id, signal_form.form_id)
            self.assertEqual(form.get_rev, signal_form.get_rev)

            signal_case = case_handler.call_args[1]['case']
            self.assertEqual(case.case_id, signal_case.case_id)
            self.assertEqual(case.get_rev, signal_case.get_rev)


@use_sql_backend
class ReprocessSubmissionStubTestsSQL(ReprocessSubmissionStubTests):
    pass


class TestReprocessDuringSubmission(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestReprocessDuringSubmission, cls).setUpClass()
        cls.domain = uuid.uuid4().hex

    def setUp(self):
        super(TestReprocessDuringSubmission, self).setUp()
        self.factory = CaseFactory(domain=self.domain)
        self.formdb = FormAccessors(self.domain)
        self.casedb = CaseAccessors(self.domain)
        self.ledgerdb = LedgerAccessors(self.domain)

    def tearDown(self):
        FormProcessorTestUtils.delete_all_cases_forms_ledgers(self.domain)
        super(TestReprocessDuringSubmission, self).tearDown()

    def test_error_saving(self):
        case_id = uuid.uuid4().hex
        form_id = uuid.uuid4().hex
        with _patch_save_to_raise_error(self):
            submit_case_blocks(
                CaseBlock(case_id=case_id, create=True, case_type='box').as_string().decode('utf-8'),
                self.domain,
                form_id=form_id
            )

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(1, len(stubs))

        form = self.formdb.get_form(form_id)
        self.assertTrue(form.is_error)

        with self.assertRaises(CaseNotFound):
            self.casedb.get_case(case_id)

        result = submit_form_locally(
            instance=form.get_xml(),
            domain=self.domain,
        )
        duplicate_form = result.xform
        self.assertTrue(duplicate_form.is_duplicate)

        case = self.casedb.get_case(case_id)
        self.assertIsNotNone(case)

        form = self.formdb.get_form(form_id)
        self.assertTrue(form.is_normal)
        self.assertIsNone(getattr(form, 'problem', None))
        self.assertEqual(duplicate_form.orig_id, form.form_id)

    def test_processing_error(self):
        case_id = uuid.uuid4().hex
        parent_case_id = uuid.uuid4().hex
        form_id = uuid.uuid4().hex
        form, _ = submit_case_blocks(
            CaseBlock(
                case_id=case_id, create=True, case_type='box',
                index={'cupboard': ('cupboard', parent_case_id)},
            ).as_string().decode('utf-8'),
            self.domain,
            form_id=form_id
        )

        self.assertTrue(form.is_error)
        self.assertTrue('InvalidCaseIndex' in form.problem)
        self.assertEqual(form.form_id, form_id)

        with self.assertRaises(CaseNotFound):
            self.casedb.get_case(case_id)

        stubs = UnfinishedSubmissionStub.objects.filter(domain=self.domain, saved=False).all()
        self.assertEqual(0, len(stubs))

        # create parent case
        submit_case_blocks(
            CaseBlock(case_id=parent_case_id, create=True, case_type='cupboard').as_string().decode('utf-8'),
            self.domain,
        )

        # re-submit form
        result = submit_form_locally(
            instance=form.get_xml(),
            domain=self.domain,
        )
        duplicate_form = result.xform
        self.assertTrue(duplicate_form.is_duplicate)

        case = self.casedb.get_case(case_id)
        self.assertIsNotNone(case)

        form = self.formdb.get_form(form_id)
        self.assertTrue(form.is_normal)
        self.assertIsNone(getattr(form, 'problem', None))
        self.assertEqual(duplicate_form.orig_id, form.form_id)


@use_sql_backend
class TestReprocessDuringSubmissionSQL(TestReprocessDuringSubmission):
    pass


@contextlib.contextmanager
def _patch_save_to_raise_error(test_class):
    sql_patch = patch(
        'corehq.form_processor.backends.sql.processor.FormProcessorSQL.save_processed_models',
        side_effect=InternalError
    )
    couch_patch = patch(
        'corehq.form_processor.backends.couch.processor.FormProcessorCouch.save_processed_models',
        side_effect=InternalError
    )
    with sql_patch, couch_patch, test_class.assertRaises(InternalError):
        yield
