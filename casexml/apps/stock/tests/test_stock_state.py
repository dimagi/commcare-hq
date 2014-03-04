from casexml.apps.stock.models import StockState, CaseDomainMapping
from casexml.apps.stock.tests.base import StockTestBase
from casexml.apps.case.models import CommCareCase
from datetime import datetime
import uuid


class StockStateTest(StockTestBase):
    def test_stock_state(self):
        self._stock_report(25, 5)
        self._stock_report(10, 0)

        state = StockState.objects.get(
            section_id='stock',
            case_id=self.case_id,
            product_id=self.product_id,
        )

        self.assertEqual(10, state.stock_on_hand)
        self.assertEqual(3.0, state.daily_consumption)

    def test_domain_mapping(self):
        # make sure there's a fake case setup for this
        case = CommCareCase(
            _id=uuid.uuid4().hex,
            domain='fakedomain',
        )
        case.save()

        with self.assertRaises(CaseDomainMapping.DoesNotExist):
            CaseDomainMapping.objects.get(case_id=case._id)

        StockState(
            section_id='stock',
            case_id=case._id,
            product_id=self.product_id,
            last_modified_date=datetime.now(),
        ).save()

        self.assertEqual(
            'fakedomain',
            CaseDomainMapping.objects.get(case_id=case._id).domain_name
        )
