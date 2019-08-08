from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from decimal import Decimal
import functools

from django.test import TestCase

from corehq.apps.commtrack.consumption import recalculate_domain_consumption
from corehq.apps.commtrack.models import StockState, CommtrackConfig, ConsumptionConfig
from corehq.apps.commtrack.tests import util
from corehq.apps.consumption.models import DefaultConsumption
from corehq.apps.consumption.shortcuts import set_default_monthly_consumption_for_domain
from corehq.apps.products.models import Product, SQLProduct
from casexml.apps.stock.models import DocDomainMapping
from casexml.apps.stock.tests.base import _stock_report
from testapps.test_pillowtop.utils import process_pillow_changes


class StockStateTest(TestCase):
    domain = 'stock-state-test'

    @classmethod
    def setUpClass(cls):
        super(StockStateTest, cls).setUpClass()
        cls.domain_obj = util.bootstrap_domain(cls.domain)
        util.bootstrap_location_types(cls.domain)
        util.bootstrap_products(cls.domain)
        cls.ct_settings = CommtrackConfig.for_domain(cls.domain)
        cls.ct_settings.use_auto_consumption = True
        cls.ct_settings.consumption_config = ConsumptionConfig(
            min_transactions=0,
            min_window=0,
            optimal_window=60,
            min_periods=0,
        )
        cls.ct_settings.save()

        cls.loc = util.make_loc('loc1', domain=cls.domain)
        cls.sp = cls.loc.linked_supply_point()
        cls.products = sorted(Product.by_domain(cls.domain), key=lambda p: p._id)

        cls.process_ledger_changes = process_pillow_changes('LedgerToElasticsearchPillow')

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        super(StockStateTest, cls).tearDownClass()

    def report(self, amount, days_ago):
        return _stock_report(
            self.domain,
            self.sp.case_id,
            self.products[0]._id,
            amount,
            days_ago
        )


class StockStateBehaviorTest(StockStateTest):

    def test_stock_state(self):
        with self.process_ledger_changes:
            self.report(25, 5)
            self.report(10, 0)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(10, state.stock_on_hand)
        self.assertEqual(3.0, state.get_daily_consumption())

    def test_stock_state_for_archived_products(self):
        self.report(10, 0)

        # make sure that this StockState existed before archive
        StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.products[0].archive()

        with self.assertRaises(StockState.DoesNotExist):
            StockState.objects.get(
                section_id='stock',
                case_id=self.sp.case_id,
                product_id=self.products[0]._id,
            )

        # should still show up in include_archived filter
        self.assertEqual(
            StockState.include_archived.get(
                section_id='stock',
                case_id=self.sp.case_id,
                product_id=self.products[0]._id,
            ).product_id,
            self.products[0]._id
        )

    def test_stock_state_for_archived_locations(self):
        self.report(10, 0)

        # make sure that this StockState existed before archive
        StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.sp.sql_location.archive()

        with self.assertRaises(StockState.DoesNotExist):
            StockState.objects.get(
                section_id='stock',
                case_id=self.sp.case_id,
                product_id=self.products[0]._id,
            )

        # should still show up in include_archived filter
        self.assertEqual(
            StockState.include_archived.get(
                section_id='stock',
                case_id=self.sp.case_id,
                product_id=self.products[0]._id,
            ).product_id,
            self.products[0]._id
        )

    def test_stock_state_for_deleted_locations(self):
        self.report(10, 0)

        # make sure that this StockState existed before delete
        StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.sp.sql_location.full_delete()

        with self.assertRaises(StockState.DoesNotExist):
            StockState.objects.get(
                section_id='stock',
                case_id=self.sp.case_id,
                product_id=self.products[0]._id,
            )

    def test_domain_mapping(self):
        # make sure there's a fake case setup for this
        with self.assertRaises(DocDomainMapping.DoesNotExist):
            DocDomainMapping.objects.get(doc_id=self.sp.case_id)

        StockState(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
            last_modified_date=datetime.utcnow(),
            sql_product=SQLProduct.objects.get(product_id=self.products[0]._id),
        ).save()

        self.assertEqual(
            self.domain,
            DocDomainMapping.objects.get(doc_id=self.sp.case_id).domain_name
        )


class StockStateConsumptionTest(StockStateTest):

    def tearDown(self):
        default = DefaultConsumption.get_domain_default(self.domain)
        if default:
            default.delete()
        super(StockStateConsumptionTest, self).tearDown()

    def test_none_with_no_defaults(self):
        # need to submit something to have a state initialized
        with self.process_ledger_changes:
            self.report(25, 0)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(None, state.get_daily_consumption())

    def test_pre_set_defaults(self):
        set_default_monthly_consumption_for_domain(self.domain, 5 * 30)
        with self.process_ledger_changes:
            self.report(25, 0)
        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(5, float(state.get_daily_consumption()))

    def test_defaults_set_after_report(self):
        with self.process_ledger_changes:
            self.report(25, 0)
        set_default_monthly_consumption_for_domain(self.domain, 5 * 30)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(5, float(state.get_daily_consumption()))

    def test_rebuild_for_domain(self):
        # 5 days, 1 transaction
        self.report(25, 5)
        self.report(10, 0)
        expected_result = Decimal(3)

        commtrack_settings = self.domain_obj.commtrack_settings

        def _update_consumption_config(min_transactions, min_window, optimal_window):
            commtrack_settings.consumption_config.min_transactions = min_transactions
            commtrack_settings.consumption_config.min_window = min_window
            commtrack_settings.consumption_config.optimal_window = optimal_window
            commtrack_settings.save()

        _reset = functools.partial(_update_consumption_config, 0, 3, 100)  # should fall in range

        tests = (
            ((0, 3, 100), expected_result),  # normal result
            ((2, 3, 100), None),   # not enough transactions
            ((2, 3, 100), None),   # not enough transactions
            ((0, 6, 100), None),   # too much time
            ((2, 3, 4), None),   # not enough time
        )
        for consumption_params, test_result in tests:
            _reset()
            recalculate_domain_consumption(self.domain)
            state = StockState.objects.get(section_id='stock', case_id=self.sp.case_id, product_id=self.products[0]._id)
            self.assertEqual(
                expected_result,
                state.daily_consumption,
                'reset state failed for arguments: {}: {} != {}'.format(
                    consumption_params, test_result, state.daily_consumption)
            )

            # just changing the config shouldn't change the state
            _update_consumption_config(*consumption_params)
            state = StockState.objects.get(section_id='stock', case_id=self.sp.case_id, product_id=self.products[0]._id)
            self.assertEqual(
                expected_result,
                state.daily_consumption,
                'update config failed for arguments: {}: {} != {}'.format(
                    consumption_params, test_result, state.daily_consumption)
            )

            # recalculating should though
            recalculate_domain_consumption(self.domain)
            state = StockState.objects.get(section_id='stock', case_id=self.sp.case_id, product_id=self.products[0]._id)
            self.assertEqual(
                test_result,
                state.daily_consumption,
                'test failed for arguments: {}: {} != {}'.format(
                    consumption_params, test_result, state.daily_consumption)
            )
