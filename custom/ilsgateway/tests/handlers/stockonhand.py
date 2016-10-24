from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from corehq.apps.sms.api import incoming
from corehq.util.translation import localize
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM, SOH_BAD_FORMAT, LANGUAGE_CONFIRM
from custom.ilsgateway.tests.handlers.utils import ILSTestScript


class ILSSoHTest(ILSTestScript):

    def setUp(self):
        super(ILSSoHTest, self).setUp()

    def test_stock_on_hand(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)
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
            response = unicode(SOH_CONFIRM)
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
            response = unicode(SOH_CONFIRM)
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

    def test_product_aliases(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        script = """
            5551234 > Hmk iucd 400
            5551234 < {}
        """.format(response)
        self.run_script(script)

        script = """
            5551234 > Hmk Depo 569
            5551234 < {}
        """.format(response)
        self.run_script(script)

        script = """
            5551234 > Hmk IMPL 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiter_standard(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        # standard spacing
        script = """
            5551234 > hmk fs100 md100 ff100 dx100 bp100 pc100 qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiter_no_spaces(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        # no spaces
        script = """
            5551234 > hmk fs100md100ff100dx100bp100pc100qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(response)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_mixed_spacing(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)
        # no spaces
        script = """
            5551234 > hmk fs100 md 100 ff100 dx  100bp   100 pc100 qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(response)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_all_spaced_out(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)
        # all space delimited
        script = """
            5551234 > hmk fs 100 md 100 ff 100 dx 100 bp 100 pc 100 qi 100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiters_commas(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        # commas
        script = """
            5551234 > hmk fs100,md100,ff100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiters_commas_and_spaces(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        # commas
        script = """
            5551234 > hmk fs100, md100, ff100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_delimiters_extra_spaces(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        # extra spaces
        script = """
            5551234 > hmk fs  100   md    100     ff      100       pc        100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_mixed_delimiters_and_spacing(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)

        # mixed - commas, spacing
        script = """
            5551234 > hmk fs100 , md100,ff 100 pc  100  qi,       1000,bp, 100, dx,100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_invalid_code(self):
        with localize('sw'):
            response = unicode(SOH_BAD_FORMAT)

        script = """
            5551234 > hmk asdds 100 ff 100
            5551234 < %(soh_bad_format)s
        """ % {'soh_bad_format': response}
        self.run_script(script)
        self.assertEqual(StockState.objects.get(
            sql_product__code='ff',
            case_id=self.facility_sp_id
        ).stock_on_hand, 100)

    def test_stock_on_hand_language_swahili(self):
        with localize('sw'):
            response = unicode(SOH_CONFIRM)
        script = """
            5551234 > hmk fs100md100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response}
        self.run_script(script)

    def test_stock_on_hand_language_english(self):
        with localize('en'):
            response = unicode(LANGUAGE_CONFIRM)
            response2 = unicode(SOH_CONFIRM)

        language_message = """
            5551234 > language en
            5551234 < {0}
        """.format(unicode(response % dict(language='English')))
        self.run_script(language_message)

        script = """
            5551234 > hmk fs100md100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": response2}
        self.run_script(script)

        with localize('sw'):
            response = unicode(LANGUAGE_CONFIRM)

        language_message = """
            5551234 > language sw
            5551234 < {0}
        """.format(unicode(response % dict(language='Swahili')))
        self.run_script(language_message)

    def test_multiline_message(self):
        quantities = {
            'fs': 100,
            'md': 100,
            'ff': 100,
            'pc': 100
        }
        message = """
            hmk
            fs 100 md 100 ff 100 pc 100
        """
        verified_number = self.user1.get_verified_number()
        msg = incoming(
            verified_number.phone_number, message, verified_number.backend_id
        )
        self.assertIsNotNone(msg)

        stock_states = StockState.objects.filter(
            case_id=self.facility_sp_id
        ).values_list('sql_product__code', 'stock_on_hand')

        for product_code, quantity in stock_states:
            self.assertEqual(quantity, quantities[product_code])
