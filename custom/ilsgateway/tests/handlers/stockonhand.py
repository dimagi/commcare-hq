from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.reminders.util import get_two_way_number_for_recipient
from corehq.apps.sms.api import incoming
from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM, SOH_BAD_FORMAT, LANGUAGE_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript
import six


class ILSSoHTest(ILSTestScript):

    def test_stock_on_hand(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)
        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)
        self.assertEqual(StockTransaction.objects.all().count(), 3)
        self.assertEqual(StockState.objects.all().count(), 3)

        quantities = [400, 569, 678]

        self.assertEqual(2, SupplyPointStatus.objects.count())
        soh_status = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.SOH_FACILITY)
        self.assertEqual(self.user1.location_id, soh_status.location_id)
        self.assertEqual(SupplyPointStatusValues.SUBMITTED, soh_status.status_value)
        la_status = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY)
        self.assertEqual(self.user1.location_id, la_status.location_id)
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, la_status.status_value)
        for idx, stock_transaction in enumerate(StockTransaction.objects.all().order_by('pk')):
            self.assertEqual(stock_transaction.stock_on_hand, quantities[idx])

    def test_stock_on_hand_stockouts(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)
        script = """
            5551234 > Hmk Id 0 Dp 0 Ip 0
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

        self.assertEqual(StockTransaction.objects.filter(case_id=self.facility_sp_id).count(), 3)
        self.assertEqual(StockState.objects.filter(case_id=self.facility_sp_id).count(), 3)

        for stock_transaction in StockTransaction.objects.filter(case_id=self.facility_sp_id):
            self.assertTrue(stock_transaction.stock_on_hand == 0)

    def test_stock_on_hand_update(self):
        with localize('sw'):
            response = six.text_type(SOH_CONFIRM)
        prod_amt_configs = [
            (('Id', 100), ('Dp', 200), ('Ip', 300)),
            (('Id', 0), ('Dp', 100), ('Ip', 200)),
            (('Id', 100), ('Dp', 0), ('Ip', 0)),
            (('Id', 50), ('Dp', 150), ('Ip', 250)),
            (('Id', 0), ('Dp', 0), ('Ip', 0)),
        ]
        pkmax = -1
        for prod_amt_config in prod_amt_configs:
            this_pkmax = pkmax
            product_string = ' '.join(['{p} {v}'.format(p=p, v=v) for p, v in prod_amt_config])
            script = """
                5551234 > Hmk {products}
                5551234 < {soh_confirm}
            """.format(
                products=product_string,
                soh_confirm=response
            )
            self.run_script(script)
            self.assertEqual(
                StockTransaction.objects.filter(
                    case_id=self.facility_sp_id,
                    type__in=['stockonhand', 'stockout'],
                    pk__gt=pkmax
                ).count(), 3
            )
            self.assertEqual(StockState.objects.count(), 3)
            for code, amt in prod_amt_config:
                ps = StockState.objects.get(
                    sql_product__code__iexact=code,
                    case_id=self.facility_sp_id
                )
                self.assertEqual(amt, ps.stock_on_hand)
                pr = StockTransaction.objects.get(
                    case_id=self.facility_sp_id,
                    pk__gt=pkmax, sql_product__code__iexact=code, type__in=['stockonhand', 'stockout']
                )
                self.assertEqual(amt, pr.stock_on_hand)
                this_pkmax = max(this_pkmax, pr.pk)
            pkmax = max(this_pkmax, pkmax)

    def test_stock_on_hand_invalid_code(self):
        with localize('sw'):
            response = six.text_type(SOH_BAD_FORMAT)

        script = """
            5551234 > hmk asdds 100 ff 100
            5551234 < %(soh_bad_format)s
        """ % {'soh_bad_format': response}
        self.run_script(script)
        self.assertEqual(StockState.objects.get(
            sql_product__code='ff',
            case_id=self.facility_sp_id
        ).stock_on_hand, 100)
