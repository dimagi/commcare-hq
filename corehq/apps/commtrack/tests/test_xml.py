from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.commtrack.models import Product
from corehq.apps.commtrack.tests.data.balances import (
    blank_balances,
    balances_with_adequate_values,
    balances_with_overstock_values,
    balances_with_stockout,
)


class CommTrackXMLTest(CommTrackTest):
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
