from decimal import Decimal
import functools
from corehq.apps.commtrack.consumption import recalculate_domain_consumption
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import SQLProduct
from casexml.apps.stock.models import DocDomainMapping
from casexml.apps.stock.tests.base import _stock_report
from corehq.apps.commtrack.tests.util import CommTrackTest
from datetime import datetime
from corehq.apps.consumption.shortcuts import set_default_monthly_consumption_for_domain


class StockStateTest(CommTrackTest):
    def report(self, amount, days_ago):
        return _stock_report(
            self.sp.case_id,
            self.products[0]._id,
            amount,
            days_ago
        )


class StockStateBehaviorTest(StockStateTest):
    def test_stock_state(self):
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
        self.sp.location.save()
        self.report(10, 0)

        # make sure that this StockState existed before archive
        StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.sp.location.archive()

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
        self.sp.location.save()
        self.report(10, 0)

        # make sure that this StockState existed before delete
        StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.sp.location.full_delete()

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
            self.domain.name,
            DocDomainMapping.objects.get(doc_id=self.sp.case_id).domain_name
        )


class StockStateConsumptionTest(StockStateTest):
    def test_none_with_no_defaults(self):
        # need to submit something to have a state initialized
        self.report(25, 0)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(None, state.get_daily_consumption())

    def test_pre_set_defaults(self):
        set_default_monthly_consumption_for_domain(self.domain.name, 5 * 30)
        self.report(25, 0)
        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp.case_id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(5, float(state.get_daily_consumption()))

    def test_defaults_set_after_report(self):
        self.report(25, 0)
        set_default_monthly_consumption_for_domain(self.domain.name, 5 * 30)

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

        commtrack_settings = self.domain.commtrack_settings
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
            recalculate_domain_consumption(self.domain.name)
            state = StockState.objects.get(section_id='stock', case_id=self.sp.case_id, product_id=self.products[0]._id)
            self.assertEqual(expected_result, state.daily_consumption,
                             'reset state failed for arguments: {}'.format(consumption_params))

            # just changing the config shouldn't change the state
            _update_consumption_config(*consumption_params)
            state = StockState.objects.get(section_id='stock', case_id=self.sp.case_id, product_id=self.products[0]._id)
            self.assertEqual(expected_result, state.daily_consumption,
                             'update config failed for arguments: {}'.format(consumption_params))

            # recalculating should though
            recalculate_domain_consumption(self.domain.name)
            state = StockState.objects.get(section_id='stock', case_id=self.sp.case_id, product_id=self.products[0]._id)
            self.assertEqual(test_result, state.daily_consumption,
                             'test failed for arguments: {}'.format(consumption_params))
