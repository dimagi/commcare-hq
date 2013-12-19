from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.commtrack.models import Product
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases
from corehq.apps.commtrack.tests.data.balances import (
    blank_balances,
    balances_with_adequate_values,
    balances_with_overstock_values,
    balances_with_stockout,
    balance_submission,
)


class CommTrackOTATest(CommTrackTest):
    def test_ota_blank_balances(self):
        user = self.reporters['fixed']

        check_xml_line_by_line(
            self,
            blank_balances(
                self.sp,
                Product.by_domain(self.domain.name).all(),
            ),
            get_ota_balance_xml(user),
        )

    def test_ota_balances_with_adequate_values(self):
        user = self.reporters['fixed']

        first_spp = self.spps[self.products.first().code]
        first_spp.current_stock = 10
        first_spp.save()

        check_xml_line_by_line(
            self,
            balances_with_adequate_values(
                self.sp,
                Product.by_domain(self.domain.name).all(),
            ),
            get_ota_balance_xml(user),
        )

    def test_ota_balances_with_overstock_values(self):
        user = self.reporters['fixed']

        first_spp = self.spps[self.products.first().code]
        first_spp.current_stock = 9001
        first_spp.save()

        check_xml_line_by_line(
            self,
            balances_with_overstock_values(
                self.sp,
                Product.by_domain(self.domain.name).all(),
            ),
            get_ota_balance_xml(user),
        )

    def test_ota_balances_stockout(self):
        user = self.reporters['fixed']

        first_spp = self.spps[self.products.first().code]
        first_spp.current_stock = 10
        first_spp.save()
        first_spp.current_stock = 0
        first_spp.save()

        check_xml_line_by_line(
            self,
            balances_with_stockout(
                self.sp,
                Product.by_domain(self.domain.name).all(),
            ),
            get_ota_balance_xml(user),
        )

class CommTrackSubmissionTest(CommTrackTest):
    def submit_stock_form(self, xml_method):
        from casexml.apps.case import settings
        settings.CASEXML_FORCE_DOMAIN_CHECK = False
        test = post_xform_to_couch(
            xml_method(
                Product.by_domain(self.domain.name).all(),
                self.reporters['fixed'],
                self.sp,
            )
        )
        test.domain = self.domain.name
        process_cases(sender="user.username", xform=test)

    def check_product_stock(self, expected):
        self.assertEqual(self.spps[self.products.first().code].current_stock, expected)

    def test_balance_submit(self):
        self.check_product_stock(None)
        self.submit_stock_form(balance_submission)
        self.check_product_stock(35)
