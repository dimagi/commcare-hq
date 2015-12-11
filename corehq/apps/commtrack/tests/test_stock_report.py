from datetime import datetime
import random
import string

from django.test import TestCase
from casexml.apps.case.tests.util import delete_all_xforms
from casexml.apps.stock.utils import get_current_ledger_transactions, get_current_ledger_state
from corehq.apps.commtrack.models import SQLProduct

from casexml.apps.stock.const import REPORT_TYPE_BALANCE
from casexml.apps.stock.models import StockReport, StockTransaction
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.interfaces.processor import FormProcessorInterface
from corehq.form_processor.parsers.ledgers.helpers import StockReportHelper, StockTransactionHelper
from couchforms.models import XFormInstance


DOMAIN_MAX_LENGTH = 25


class StockReportDomainTest(TestCase):
    def _get_name_for_domain(self):
        return ''.join(
            random.choice(string.ascii_lowercase)
            for _ in range(DOMAIN_MAX_LENGTH)
        )

    def create_report(self, transactions=None, tag=None, date=None):
        form = XFormInstance(domain=self.domain)
        form.save()
        report = StockReportHelper.make_from_form(
            form,
            date or datetime.utcnow(),
            tag or REPORT_TYPE_BALANCE,
            transactions or [],
        )
        return report, form

    def _create_models_for_stock_report_helper(self, stock_report_helper):
        models_to_update = self.ledger_processor.get_models_to_update(stock_report_helper)
        if models_to_update:
            models_to_update.commit()

    def setUp(self):
        self.case_ids = {'c1': 10, 'c2': 30, 'c3': 50}
        self.section_ids = {'s1': 2, 's2': 9}
        self.product_ids = {'p1': 1, 'p2': 3, 'p3': 5}

        self.domain = self._get_name_for_domain()
        self.ledger_processor = FormProcessorInterface(domain=self.domain).ledger_processor
        create_domain(self.domain)

        SQLProduct.objects.bulk_create([
            SQLProduct(product_id=id) for id in self.product_ids
        ])

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
                            quantity=bal
                        )
                    )
                    self.transactions.setdefault(case, {}).setdefault(section, {})[product] = bal

        self.new_stock_report, self.form = self.create_report(transactions_flat)
        self._create_models_for_stock_report_helper(self.new_stock_report)

    def tearDown(self):
        delete_all_xforms()
        StockReport.objects.all().delete()
        StockTransaction.objects.all().delete()

    def test_stock_report(self):
        self.create_report()
        filtered_stock_report = StockReport.objects.filter(domain=self.domain)
        self.assertEquals(filtered_stock_report.count(), 1)
        stock_report = filtered_stock_report.get()
        self.assertEquals(stock_report.form_id, self.form._id)
        self.assertEquals(stock_report.domain, self.domain)

    def test_get_current_ledger_transactions(self):
        for case in self.case_ids:
            transactions = get_current_ledger_transactions(case)
            for section, products in transactions.items():
                for product, trans in products.items():
                    self.assertEqual(trans.stock_on_hand, self.transactions[case][section][product])

    def _validate_case_data(self, data, expected):
        for section, products in data.items():
            for product, trans in products.items():
                self.assertEqual(trans.stock_on_hand, expected[section][product])

    def _test_get_current_ledger_transactions(self, tester_fn):
        tester_fn(self.transactions)

        date = datetime.utcnow()
        report, _ = self.create_report([
            StockTransactionHelper(
                case_id='c1',
                section_id='s1',
                product_id='p1',
                action='soh',
                quantity=864)
        ], date=date)
        self._create_models_for_stock_report_helper(report)

        # create second report with the same date
        # results should have this transaction and not the previous one
        report, _ = self.create_report([
            StockTransactionHelper(
                case_id='c1',
                section_id='s1',
                product_id='p1',
                action='soh',
                quantity=1)
        ], date=date)
        self._create_models_for_stock_report_helper(report)

        new_trans = self.transactions.copy()
        new_trans['c1']['s1']['p1'] = 1

        tester_fn(new_trans)

    def test_get_current_ledger_transactions(self):
        def test_transactions(expected):
            for case in self.case_ids:
                transactions = get_current_ledger_transactions(case)
                self._validate_case_data(transactions, expected[case])

        self._test_get_current_ledger_transactions(test_transactions)

        self.assertEqual({}, get_current_ledger_transactions('non-existent'))

    def test_get_current_ledger_state(self):
        def test_transactions(expected):
            state = get_current_ledger_state(self.case_ids.keys())
            for case, sections in state.items():
                self._validate_case_data(sections, expected[case])

        self._test_get_current_ledger_transactions(test_transactions)

        self.assertEqual({}, get_current_ledger_state([]))
