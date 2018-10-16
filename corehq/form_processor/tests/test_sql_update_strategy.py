from django.test import TestCase
from freezegun import freeze_time
from mock import patch
from corehq.util.soft_assert.core import SoftAssert

from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.backends.sql.update_strategy import SqlCaseUpdateStrategy
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import (
    CommCareCaseSQL,
    CaseTransaction,
    RebuildWithReason,
)
from corehq.form_processor.utils import TestFormMetadata
from corehq.form_processor.tests.utils import use_sql_backend, FormProcessorTestUtils
from corehq.util.test_utils import get_form_ready_to_save

import uuid
from datetime import datetime


@use_sql_backend
class SqlUpdateStrategyTest(TestCase):
    DOMAIN = 'update-strategy-test-' + uuid.uuid4().hex
    USER_ID = 'mr_wednesday_'

    @classmethod
    def setUpClass(cls):
        super(SqlUpdateStrategyTest, cls).setUpClass()
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_sql_cases()

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_sql_forms()
        FormProcessorTestUtils.delete_all_sql_cases()
        super(SqlUpdateStrategyTest, cls).tearDownClass()

    @patch.object(SoftAssert, '_call')
    def test_reconcile_transactions(self, soft_assert_mock):
        with freeze_time("2018-10-10"):
            case = self._create_case()

        with freeze_time("2018-10-11"):
            new_old_xform = self._create_form()
        with freeze_time("2018-10-08"):
            new_old_trans = self._create_case_transaction(case, new_old_xform)
        with freeze_time("2018-10-11"):
            case.track_create(new_old_trans)
            FormProcessorSQL.save_processed_models(ProcessedForms(new_old_xform, []), [case])

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertTrue(update_strategy.reconcile_transactions_if_necessary())
        for call in soft_assert_mock.call_args_list:
            self.assertNotIn('ReconciliationError', call[0][1])

        CaseAccessorSQL.save_case(case)

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertFalse(update_strategy.reconcile_transactions_if_necessary())
        self._check_for_reconciliation_error_soft_assert(soft_assert_mock)

    def test_reconcile_not_necessary(self):
        with freeze_time("2018-10-10"):
            case = self._create_case()

        with freeze_time("2018-10-11"):
            new_old_xform = self._create_form()
            new_old_trans = self._create_case_transaction(case, new_old_xform)
            case.track_create(new_old_trans)
            FormProcessorSQL.save_processed_models(ProcessedForms(new_old_xform, []), [case])

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertFalse(update_strategy.reconcile_transactions_if_necessary())

    def test_ignores_before_rebuild_transaction(self):
        with freeze_time("2018-10-10"):
            case = self._create_case()

        with freeze_time("2018-10-11"):
            new_old_xform = self._create_form()
        with freeze_time("2018-10-08"):
            new_old_trans = self._create_case_transaction(case, new_old_xform)
        with freeze_time("2018-10-11"):
            case.track_create(new_old_trans)
            FormProcessorSQL.save_processed_models(ProcessedForms(new_old_xform, []), [case])

        self.assertFalse(case.check_transaction_order())

        with freeze_time("2018-10-13"):
            new_rebuild_xform = self._create_form()
            rebuild_detail = RebuildWithReason(reason="shadow's golden coin")
            rebuild_transaction = CaseTransaction.rebuild_transaction(case, rebuild_detail)
            case.track_create(rebuild_transaction)
            FormProcessorSQL.save_processed_models(ProcessedForms(new_rebuild_xform, []), [case])

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertFalse(update_strategy.reconcile_transactions_if_necessary())

    def _create_form(self, user_id=None, received_on=None):
        """
        Create the models directly so that these tests aren't dependent on any
        other apps.
        :return: XFormInstanceSQL
        """
        user_id = user_id or 'mr_wednesday'
        received_on = received_on or datetime.utcnow()

        metadata = TestFormMetadata(
            domain=self.DOMAIN,
            received_on=received_on,
            user_id=user_id
        )
        form = get_form_ready_to_save(metadata)

        return form

    def _create_case_transaction(self, case, form=None, submitted_on=None, action_types=None):
        form = form or self._create_form()
        submitted_on = submitted_on or datetime.utcnow()

        return CaseTransaction.form_transaction(case, form, submitted_on, action_types)

    def _create_case(self, case_type=None, user_id=None, case_id=None):
        case_id = case_id or uuid.uuid4().hex
        user_id = user_id or 'mr_wednesday'
        utcnow = datetime.utcnow()

        case = CommCareCaseSQL(
            case_id=case_id,
            domain=self.DOMAIN,
            type=case_type or '',
            owner_id=user_id,
            opened_on=utcnow,
            modified_on=utcnow,
            modified_by=utcnow,
            server_modified_on=utcnow
        )

        form = self._create_form(user_id, utcnow)
        case.track_create(self._create_case_transaction(case, form, utcnow, action_types=[128]))
        FormProcessorSQL.save_processed_models(ProcessedForms(form, []), [case])

        return CaseAccessorSQL.get_case(case_id)

    def _check_for_reconciliation_error_soft_assert(self, soft_assert_mock):
        for call in soft_assert_mock.call_args_list:
            self.assertNotIn('ReconciliationError', call[0][1])
        soft_assert_mock.reset_mock()
