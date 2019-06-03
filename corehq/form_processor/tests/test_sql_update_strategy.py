from __future__ import absolute_import, unicode_literals

from django.test import TestCase
from freezegun import freeze_time
from mock import patch
from testil import eq
from corehq.util.soft_assert.core import SoftAssert

from casexml.apps.case.exceptions import ReconciliationError
from casexml.apps.case.xml.parser import CaseUpdateAction, KNOWN_PROPERTIES
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
        """ tests a transanction with an early client date and late server date """
        with freeze_time("2018-10-10"):
            case = self._create_case()

        with freeze_time("2018-10-11"):
            new_old_xform = self._create_form()
        with freeze_time("2018-10-08"):
            new_old_trans = self._create_case_transaction(case, new_old_xform)
        with freeze_time("2018-10-11"):
            self._save(new_old_xform, case, new_old_trans)

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertTrue(update_strategy.reconcile_transactions_if_necessary())
        self._check_for_reconciliation_error_soft_assert(soft_assert_mock)

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
            self._save(new_old_xform, case, new_old_trans)

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
            self._save(new_old_xform, case, new_old_trans)

        self.assertFalse(case.check_transaction_order())

        with freeze_time("2018-10-13"):
            new_rebuild_xform = self._create_form()
            rebuild_detail = RebuildWithReason(reason="shadow's golden coin")
            rebuild_transaction = CaseTransaction.rebuild_transaction(case, rebuild_detail)
            self._save(new_rebuild_xform, case, rebuild_transaction)

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertFalse(update_strategy.reconcile_transactions_if_necessary())

    def test_first_transaction_not_create(self):
        with freeze_time("2018-10-10"):
            case = self._create_case()

        with freeze_time("2018-10-08"):
            new_old_xform = self._create_form()
            new_old_trans = self._create_case_transaction(case, new_old_xform)
            self._save(new_old_xform, case, new_old_trans)

        self.assertTrue(case.check_transaction_order())

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertRaises(ReconciliationError, update_strategy.reconcile_transactions)

    @patch.object(SoftAssert, '_call')
    def test_reconcile_transactions_within_fudge_factor(self, soft_assert_mock):
        """ tests a transanction with an early client date and late server date """
        with freeze_time("2018-10-10"):
            case = self._create_case()

        with freeze_time("2018-10-11 06:00"):
            new_old_xform = self._create_form()
        with freeze_time("2018-10-10 18:00"):
            new_old_trans = self._create_case_transaction(case, new_old_xform)
        with freeze_time("2018-10-11 06:00"):
            self._save(new_old_xform, case, new_old_trans)

        with freeze_time("2018-10-11"):
            new_old_xform = self._create_form()
            new_old_trans = self._create_case_transaction(case, new_old_xform)
            self._save(new_old_xform, case, new_old_trans)

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertTrue(update_strategy.reconcile_transactions_if_necessary())
        self._check_for_reconciliation_error_soft_assert(soft_assert_mock)

        CaseAccessorSQL.save_case(case)

        case = CaseAccessorSQL.get_case(case.case_id)
        update_strategy = SqlCaseUpdateStrategy(case)
        self.assertFalse(update_strategy.reconcile_transactions_if_necessary())
        self._check_for_reconciliation_error_soft_assert(soft_assert_mock)

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
        trans = self._create_case_transaction(case, form, utcnow, action_types=[128])
        self._save(form, case, trans)

        return CaseAccessorSQL.get_case(case_id)

    def _save(self, form, case, transaction):
        case.track_create(transaction)
        FormProcessorSQL.save_processed_models(
            ProcessedForms(form, []),
            [case],
            # disable publish to Kafka to avoid intermittent errors caused by
            # the nexus of kafka's consumer thread and freeze_time
            publish_to_kafka=False,
        )

    def _check_for_reconciliation_error_soft_assert(self, soft_assert_mock):
        for call in soft_assert_mock.call_args_list:
            self.assertNotIn('ReconciliationError', call[0][1])
        soft_assert_mock.reset_mock()


def test_update_known_properties_with_empty_values():
    def test(prop):
        case = SqlCaseUpdateStrategy.case_implementation_class()
        setattr(case, prop, "value")
        action = CaseUpdateAction(block=None, **{prop: ""})

        SqlCaseUpdateStrategy(case)._update_known_properties(action)

        eq(getattr(case, prop), "")

    # verify that at least one property will be tested
    assert any(v is not None for v in KNOWN_PROPERTIES.values()), KNOWN_PROPERTIES

    for prop, default in KNOWN_PROPERTIES.items():
        if default is not None:
            yield test, prop
