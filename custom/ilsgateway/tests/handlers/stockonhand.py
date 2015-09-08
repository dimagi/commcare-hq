from casexml.apps.stock.models import StockTransaction
from corehq.apps.commtrack.models import StockState
from custom.ilsgateway.models import SupplyPointStatus, SupplyPointStatusTypes, SupplyPointStatusValues
from custom.ilsgateway.tanzania.reminders import SOH_CONFIRM, SOH_PARTIAL_CONFIRM, SOH_BAD_FORMAT
from custom.ilsgateway.tests import ILSTestScript
from custom.ilsgateway.tests.handlers.utils import add_products


class ILSSoHTest(ILSTestScript):

    def setUp(self):
        super(ILSSoHTest, self).setUp()

    def test_stock_on_hand(self):
        script = """
            5551234 > Hmk Id 400 Dp 569 Ip 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)
        self.assertEqual(StockTransaction.objects.all().count(), 3)
        self.assertEqual(StockState.objects.all().count(), 3)

        self.assertEqual(2, SupplyPointStatus.objects.count())
        soh_status = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.SOH_FACILITY)
        self.assertEqual(self.user1.location_id, soh_status.location_id)
        self.assertEqual(SupplyPointStatusValues.SUBMITTED, soh_status.status_value)
        la_status = SupplyPointStatus.objects.get(status_type=SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY)
        self.assertEqual(self.user1.location_id, la_status.location_id)
        self.assertEqual(SupplyPointStatusValues.REMINDER_SENT, la_status.status_value)
        for stock_transaction in StockTransaction.objects.all():
            self.assertTrue(stock_transaction.stock_on_hand != 0)

    def test_stock_on_hand_stockouts(self):
        script = """
            5551234 > Hmk Id 0 Dp 0 Ip 0
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

        self.assertEqual(StockTransaction.objects.all().count(), 3)
        self.assertEqual(StockState.objects.all().count(), 3)

        for stock_transaction in StockTransaction.objects.all():
            self.assertTrue(stock_transaction.stock_on_hand == 0)

    def test_stock_on_hand_update(self):
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
                soh_confirm=unicode(SOH_CONFIRM)
            )
            self.run_script(script)
            self.assertEqual(
                StockTransaction.objects.filter(type__in=['stockonhand', 'stockout'], pk__gt=pkmax).count(), 3
            )
            self.assertEqual(StockState.objects.count(), 3)
            for code, amt in prod_amt_config:
                ps = StockState.objects.get(sql_product__code__iexact=code)
                self.assertEqual(amt, ps.stock_on_hand)
                pr = StockTransaction.objects.get(
                    pk__gt=pkmax, sql_product__code__iexact=code, type__in=['stockonhand', 'stockout']
                )
                this_pkmax = max(this_pkmax, pr.pk)
            pkmax = max(this_pkmax, pkmax)

    def test_stock_on_hand_partial_report(self):
        add_products(self.loc1.sql_location, ["id", "dp", "fs", "md", "ff", "dx", "bp", "pc", "qi"])
        script = """
            5551234 > Hmk Id 400
            5551234 < {}
        """.format(SOH_PARTIAL_CONFIRM % {
            'contact_name': self.user1.full_name,
            'facility_name': self.loc1.name,
            'product_list': 'bp dp dx ff fs md pc qi'
        })
        self.run_script(script)
        script = """
            5551234 > Hmk Dp 569 ip 454 ff 5655
            5551234 < {}
        """.format(SOH_PARTIAL_CONFIRM % {
            'contact_name': self.user1.full_name,
            'facility_name': self.loc1.name,
            'product_list': 'bp dx fs md pc qi'
        })
        self.run_script(script)

        script = """
            5551234 > Hmk Bp 343 Dx 565 Fs 2322 Md 100 Pc 8778 Qi 34
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_product_aliases(self):

        add_products(self.loc1.sql_location, ["id", "dp", "ip"])
        script = """
            5551234 > Hmk iucd 400
            5551234 < {}
        """.format(SOH_PARTIAL_CONFIRM % {
            'contact_name': self.user1.full_name,
            'facility_name': self.loc1.name,
            'product_list': 'dp ip'
        })
        self.run_script(script)

        script = """
            5551234 > Hmk Depo 569
            5551234 < {}
        """.format(SOH_PARTIAL_CONFIRM % {
            'contact_name': self.user1.full_name,
            'facility_name': self.loc1.name,
            'product_list': 'ip'
        })
        self.run_script(script)

        script = """
            5551234 > Hmk IMPL 678
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_delimiter_standard(self):
        product_codes = ["fs", "md", "ff", "dx", "bp", "pc", "qi"]
        add_products(self.loc1.sql_location, product_codes)

        #standard spacing
        script = """
            5551234 > hmk fs100 md100 ff100 dx100 bp100 pc100 qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_delimiter_no_spaces(self):
        product_codes = ["fs", "md", "ff", "dx", "bp", "pc", "qi"]
        add_products(self.loc1.sql_location, product_codes)

        #no spaces
        script = """
            5551234 > hmk fs100md100ff100dx100bp100pc100qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_mixed_spacing(self):
        product_codes = ["fs", "md", "ff", "dx", "bp", "pc", "qi"]
        add_products(self.loc1.sql_location, product_codes)

        #no spaces
        script = """
            5551234 > hmk fs100 md 100 ff100 dx  100bp   100 pc100 qi100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_all_spaced_out(self):
        product_codes = ["fs", "md", "ff", "dx", "bp", "pc", "qi"]
        add_products(self.loc1.sql_location, product_codes)

        #all space delimited
        script = """
            5551234 > hmk fs 100 md 100 ff 100 dx 100 bp 100 pc 100 qi 100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_commas(self):
        product_codes = ["fs", "md", "ff"]
        add_products(self.loc1.sql_location, product_codes)

        #commas
        script = """
            5551234 > hmk fs100,md100,ff100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_commas_and_spaces(self):
        product_codes = ["fs", "md", "ff"]
        add_products(self.loc1.sql_location, product_codes)

        #commas
        script = """
            5551234 > hmk fs100, md100, ff100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_delimiters_extra_spaces(self):
        product_codes = ["fs", "md", "ff", "pc"]
        add_products(self.loc1.sql_location, product_codes)

        #extra spaces
        script = """
            5551234 > hmk fs  100   md    100     ff      100       pc        100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_CONFIRM)}
        self.run_script(script)

    def test_stock_on_hand_mixed_delimiters_and_spacing(self):
        product_codes = ["fs", "md", "ff", "pc", "qi", "bp", "dx"]
        add_products(self.loc1.sql_location, product_codes)

        #mixed - commas, spacing
        script = """
            5551234 > hmk fs100 , md100,ff 100 pc  100  qi,       1000,bp, 100, dx,100
            5551234 < %(soh_confirm)s
        """ % {"soh_confirm": unicode(SOH_PARTIAL_CONFIRM) % {
            "contact_name": self.user1.full_name, "facility_name": self.loc1.name, "product_list": "bp dx qi"
        }}
        self.run_script(script)

    def test_stock_on_hand_invalid_code(self):
        script = """
            5551234 > hmk asdds 100 ff 100
            5551234 < %(soh_bad_format)s
        """ % {'soh_bad_format': unicode(SOH_BAD_FORMAT)}
        self.run_script(script)

        self.assertEqual(StockState.objects.get(sql_product__code='ff').stock_on_hand, 100)
