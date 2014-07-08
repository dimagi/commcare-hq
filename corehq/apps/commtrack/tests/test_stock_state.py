from corehq.apps.commtrack.models import StockState
from casexml.apps.stock.models import DocDomainMapping
from casexml.apps.stock.tests.base import _stock_report
from corehq.apps.commtrack.tests.util import CommTrackTest
from corehq.apps.commtrack.const import DAYS_IN_MONTH
from datetime import datetime
from corehq.apps.consumption.shortcuts import set_default_consumption_for_domain


class StockStateTest(CommTrackTest):
    def report(self, amount, days_ago):
        return _stock_report(
            self.sp._id,
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
            case_id=self.sp._id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(10, state.stock_on_hand)
        self.assertEqual(3.0, state.get_daily_consumption())

    def test_domain_mapping(self):
        # make sure there's a fake case setup for this
        with self.assertRaises(DocDomainMapping.DoesNotExist):
            DocDomainMapping.objects.get(doc_id=self.sp._id)

        StockState(
            section_id='stock',
            case_id=self.sp._id,
            product_id=self.products[0]._id,
            last_modified_date=datetime.now(),
        ).save()

        self.assertEqual(
            self.domain.name,
            DocDomainMapping.objects.get(doc_id=self.sp._id).domain_name
        )


class StockStateConsumptionTest(StockStateTest):
    def test_none_with_no_defaults(self):
        # need to submit something to have a state initialized
        self.report(25, 0)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp._id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(None, state.get_daily_consumption())

    def test_pre_set_defaults(self):
        set_default_consumption_for_domain(self.domain.name, 50)
        self.report(25, 0)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp._id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(50, float(state.get_daily_consumption()))

    def test_defaults_set_after_report(self):
        self.report(25, 0)
        set_default_consumption_for_domain(self.domain.name, 50)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.sp._id,
            product_id=self.products[0]._id,
        )

        self.assertEqual(50, float(state.get_daily_consumption()))
