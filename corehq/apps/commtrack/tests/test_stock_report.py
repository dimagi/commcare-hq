from __future__ import absolute_import
from __future__ import unicode_literals
import uuid
from datetime import datetime
import random
import string

from django.test import TestCase
from casexml.apps.case.tests.util import delete_all_ledgers, delete_all_xforms
from corehq.apps.commtrack.models import SQLProduct

from casexml.apps.stock.const import REPORT_TYPE_BALANCE
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.commtrack.processing import StockProcessingResult
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.interfaces.dbaccessors import LedgerAccessors
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.ledgers.helpers import StockReportHelper, StockTransactionHelper
from corehq.form_processor.tests.utils import run_with_all_backends
from corehq.form_processor.utils import get_simple_wrapped_form
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.form_processor.utils.xform import TestFormMetadata
from six.moves import range

DOMAIN_MAX_LENGTH = 25


def _get_name_for_domain():
    return ''.join(
        random.choice(string.ascii_lowercase)
        for _ in range(DOMAIN_MAX_LENGTH)
    )


class StockReportDomainTest(TestCase):
    def create_report(self, transactions=None, tag=None, date=None):
        form = get_simple_wrapped_form(uuid.uuid4().hex, metadata=TestFormMetadata(domain=self.domain))
        report = StockReportHelper.make_from_form(
            form,
            date or datetime.utcnow(),
            tag or REPORT_TYPE_BALANCE,
            transactions or [],
        )
        return report, form

    def _create_models_for_stock_report_helper(self, form, stock_report_helper):
        processing_result = StockProcessingResult(form, stock_report_helpers=[stock_report_helper])
        processing_result.populate_models()
        if should_use_sql_backend(self.domain):
            from corehq.form_processor.backends.sql.dbaccessors import LedgerAccessorSQL
            LedgerAccessorSQL.save_ledger_values(processing_result.models_to_save)
        else:
            processing_result.commit()

    @classmethod
    def setUpClass(cls):
        super(StockReportDomainTest, cls).setUpClass()
        cls.case_ids = {'c1': 10, 'c2': 30, 'c3': 50}
        cls.section_ids = {'s1': 2, 's2': 9}
        cls.product_ids = {'p1': 1, 'p2': 3, 'p3': 5}

        SQLProduct.objects.bulk_create([
            SQLProduct(product_id=id) for id in cls.product_ids
        ])

    @classmethod
    def tearDownClass(cls):
        SQLProduct.objects.all().delete()
        super(StockReportDomainTest, cls).tearDownClass()

    def setUp(self):
        super(StockReportDomainTest, self).setUp()
        self.domain = _get_name_for_domain()
        self.ledger_processor = FormProcessorInterface(domain=self.domain).ledger_processor
        create_domain(self.domain)

        transactions_flat = []
        self.transactions = {}
        for case, c_bal in self.case_ids.items():
            for section, s_bal in self.section_ids.items():
                for product, p_bal in self.product_ids.items():
                    bal = c_bal + s_bal + p_bal
                    transactions_flat.append(
                        StockTransactionHelper(
                            case_id=case,
                            section_id=section,
                            product_id=product,
                            action='soh',
                            quantity=bal,
                            timestamp=datetime.utcnow()
                        )
                    )
                    self.transactions.setdefault(case, {}).setdefault(section, {})[product] = bal

        self.new_stock_report, self.form = self.create_report(transactions_flat)
        self._create_models_for_stock_report_helper(self.form, self.new_stock_report)

    def tearDown(self):
        delete_all_xforms()
        delete_all_ledgers()
        StockReport.objects.all().delete()
        StockTransaction.objects.all().delete()
        super(StockReportDomainTest, self).tearDown()

    def test_stock_report(self):
        self.create_report()
        filtered_stock_report = StockReport.objects.filter(domain=self.domain)
        self.assertEquals(filtered_stock_report.count(), 1)
        stock_report = filtered_stock_report.get()
        self.assertEquals(stock_report.form_id, self.form._id)
        self.assertEquals(stock_report.domain, self.domain)

    @run_with_all_backends
    def test_get_case_ledger_state(self):
        for case_id in self.case_ids:
            state = LedgerAccessors(self.domain).get_case_ledger_state(case_id)
            for section, products in state.items():
                for product, state in products.items():
                    self.assertEqual(state.stock_on_hand, self.transactions[case_id][section][product])

    def _validate_case_data(self, data, expected):
        for section, products in data.items():
            for product, state in products.items():
                self.assertEqual(state.stock_on_hand, expected[section][product])

    def _test_get_current_ledger_transactions(self, tester_fn):
        tester_fn(self.transactions)

        date = datetime.utcnow()
        report, _ = self.create_report([
            StockTransactionHelper(
                case_id='c1',
                section_id='s1',
                product_id='p1',
                action='soh',
                quantity=864,
                timestamp=datetime.utcnow())
        ], date=date)
        self._create_models_for_stock_report_helper(self.form, report)

        # create second report with the same date
        # results should have this transaction and not the previous one
        report, _ = self.create_report([
            StockTransactionHelper(
                case_id='c1',
                section_id='s1',
                product_id='p1',
                action='soh',
                quantity=1,
                timestamp=datetime.utcnow())
        ], date=date)
        self._create_models_for_stock_report_helper(self.form, report)

        new_trans = self.transactions.copy()
        new_trans['c1']['s1']['p1'] = 1

        tester_fn(new_trans)

    @run_with_all_backends
    def test_get_case_ledger_state_1(self):
        def test_transactions(expected):
            for case_id in self.case_ids:
                state = LedgerAccessors(self.domain).get_case_ledger_state(case_id)
                self._validate_case_data(state, expected[case_id])

        self._test_get_current_ledger_transactions(test_transactions)

        self.assertEqual({}, LedgerAccessors(self.domain).get_case_ledger_state('non-existent'))

    @run_with_all_backends
    def test_get_current_ledger_state(self):
        def test_transactions(expected):
            state = LedgerAccessors(self.domain).get_current_ledger_state(list(self.case_ids))
            for case_id, sections in state.items():
                self._validate_case_data(sections, expected[case_id])

        self._test_get_current_ledger_transactions(test_transactions)

        self.assertEqual({}, LedgerAccessors(self.domain).get_current_ledger_state([]))
