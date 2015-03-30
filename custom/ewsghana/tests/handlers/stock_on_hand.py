from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from custom.ewsghana.tests.handlers.utils import EWSScriptTest, TEST_DOMAIN


class StockOnHandTest(EWSScriptTest):

    def test_stock_on_hand(self):
        a = """
           5551234 > soh lf 31.0
           5551234 < Dear stella, thank you for reporting the commodities you have in stock.
           5551234 > soh lf 31.0 mc 25.0
           5551234 < Dear stella, thank you for reporting the commodities you have in stock.
           5551234 > SOH LF 31.0 MC 25.0
           5551234 < Dear stella, thank you for reporting the commodities you have in stock.
           """
        self.run_script(a)

    def test_stockout(self):
        a = """
           5551234 > soh lf 0.0 mc 0.0
           5551234 < Dear stella, these items are stocked out: lf mc.
           """
        self.run_script(a)

    def test_stockout_no_consumption(self):
        a = """
           5551234 > soh ng 0.0
           5551234 < Dear stella, these items are stocked out: ng.
           """
        self.run_script(a)

    def test_low_supply(self):
        a = """
           5551234 > soh lf 7.0 mc 9.0
           5551234 < Dear stella, these items need to be reordered: lf mc.
           """
        self.run_script(a)

    def test_low_supply_no_consumption(self):
        a = """
           5551234 > soh ng 3.0
           5551234 < Dear stella, thank you for reporting the commodities you have in stock.
           """
        self.run_script(a)

    def test_over_supply(self):
        a = """
            5551234 > soh lf 100.0 mc 100.0
            5551234 < Dear stella, these items are overstocked: lf mc. The district admin has been informed.
        """
        self.run_script(a)

    def test_soh_and_receipt(self):
        a = """
           5551234 > soh lf 15.20 mc 25.0
           5551234 < Dear stella, thank you for reporting the commodities you have. You received lf 20.
           """
        self.run_script(a)

    def test_combined1(self):
        second_message = "Dear super, Test RMS is experiencing the following problems: stockouts Lofem; " \
                         "below reorder level Male Condom"
        a = """
           5551234 > soh lf 0.0 mc 1.0
           222222  < %s
           5551234 < Dear stella, these items are stocked out: lf. these items need to be reordered: mc.
           """ % second_message
        self.run_script(a)

    def test_combined2(self):
        second_message = "Dear super, Test RMS is experiencing the following problems: stockouts Male Condom; " \
                         "below reorder level Micro-G"
        fifth_message = "Dear super, Test RMS is experiencing the following problems: stockouts Male Condom; " \
                        "below reorder level Micro-G; overstocked Lofem"
        a = """
           5551234 > soh mc 0.0 mg 1.0
           222222 < %s
           5551234 < Dear stella, these items are stocked out: mc. these items need to be reordered: mg.
           5551234 > soh mc 0.0 mg 1.0 lf 100.0
           222222 < %s
           5551234 < Dear stella, these items are stocked out: mc. these items need to be reordered: mg.
           """ % (second_message, fifth_message)
        self.run_script(a)

    def test_combined3(self):
        second_message = "Dear super, Test RMS is experiencing the following problems: stockouts Male Condom; " \
                         "below reorder level Micro-G"
        fifth_message = "Dear super, Test RMS is experiencing the following problems: " \
                        "below reorder level Male Condom Micro-G"
        a = """
           5551234 > soh mc 0.0 mg 1.0 ng 300.0
           222222 < %s
           5551234 < Dear stella, these items are stocked out: mc. these items need to be reordered: mg.
           5551234 > soh mc 0.2 mg 1.0 ng 300.0
           222222 < %s
           5551234 <  Dear stella, these items need to be reordered: mc mg.
           """ % (second_message, fifth_message)
        self.run_script(a)

    def test_combined4(self):
        second_message = "Dear super, Test RMS is experiencing the following problems: stockouts Male Condom; " \
                         "below reorder level Micro-G"
        a = """
           5551234 > soh mc 0.0 mg 1.0 ng 300.0
           222222 < %s
           5551234 < Dear stella, these items are stocked out: mc. these items need to be reordered: mg.
           """ % second_message
        self.run_script(a)

    def test_combined5(self):
        a = """
           5551234 > soh mc 25.0 lf 31.0 mg 300.0
           222222 < Dear super, Test RMS is experiencing the following problems: overstocked Micro-G
           5551234 < Dear stella, these items are overstocked: mg. The district admin has been informed.
           """
        self.run_script(a)

    def test_incomplete_report(self):
        ng = SQLProduct.objects.get(domain=TEST_DOMAIN, code='ng')
        jd = SQLProduct.objects.get(domain=TEST_DOMAIN, code='jd')
        mg = SQLProduct.objects.get(domain=TEST_DOMAIN, code='mg')
        location = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='garms')
        location.products = [ng, jd, mg]
        location.save()
        a = """
            5551234 > soh mg 20.0
            5551234 < Dear stella, still missing jd ng.
            5551234 > soh jd 20.0
            5551234 < Dear stella, still missing ng.
            5551234 > soh ng 20.0
            5551234 < Dear stella, thank you for reporting the commodities you have in stock.
        """
        self.run_script(a)

    def test_incomplete_report2(self):
        ng = SQLProduct.objects.get(domain=TEST_DOMAIN, code='ng')
        jd = SQLProduct.objects.get(domain=TEST_DOMAIN, code='jd')
        mg = SQLProduct.objects.get(domain=TEST_DOMAIN, code='mg')
        location = SQLLocation.objects.get(domain=TEST_DOMAIN, site_code='garms')
        location.products = [ng, jd, mg]
        location.save()
        a = """
            5551234 > soh mg 20.0 jd 20.0 ng 20.0
            5551234 < Dear stella, thank you for reporting the commodities you have in stock.
        """
        self.run_script(a)
