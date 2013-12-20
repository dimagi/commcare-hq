from corehq.apps.commtrack.tests.util import CommTrackTest, get_ota_balance_xml
from casexml.apps.case.tests.util import check_xml_line_by_line
from corehq.apps.commtrack.models import Product
from couchforms.util import post_xform_to_couch
from casexml.apps.case.signals import process_cases
from corehq.apps.commtrack.tests.util import make_loc, make_supply_point, make_supply_point_product
from corehq.apps.commtrack.tests.data.balances import (
    blank_balances,
    balances_with_adequate_values,
    balances_with_overstock_values,
    balances_with_stockout,
    balance_submission,
    submission_wrap,
    balance_submission,
    transfer_dest_only,
    transfer_source_only,
    transfer_both,
    transfer_neither,
    balance_first,
    transfer_first,
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
    def submit_xml_form(self, xml_method):
        from casexml.apps.case import settings
        settings.CASEXML_FORCE_DOMAIN_CHECK = False
        test = post_xform_to_couch(
            submission_wrap(
                Product.by_domain(self.domain.name).all(),
                self.reporters['fixed'],
                self.sp,
                self.sp2,
                xml_method,
            )
        )
        test.domain = self.domain.name
        process_cases(sender="user.username", xform=test)

    def check_product_stock(self, expected, spp=None):
        spp = spp or self.first_spp
        self.assertEqual(spp.current_stock, expected)

    def setUp(self):
        super(CommTrackSubmissionTest, self).setUp()
        self.first_spp = self.spps[self.products.first().code]
        self.first_spp.current_stock = 10
        self.first_spp.save()

        loc2 = make_loc('loc1')
        self.sp2 = make_supply_point(self.domain.name, loc2)
        self.second_spp = make_supply_point_product(self.sp2, self.products.first()._id)
        self.second_spp.current_stock = 10
        self.second_spp.save()

        # make sure we are starting from an expected state
        self.check_product_stock(10)
        self.check_product_stock(10, self.second_spp)

    def test_balance_submit(self):
        self.submit_xml_form(balance_submission)
        self.check_product_stock(35)

    def test_transfer_dest_only(self):
        self.submit_xml_form(transfer_dest_only)
        self.check_product_stock(48)

    def test_transfer_source_only(self):
        self.submit_xml_form(transfer_source_only)
        self.check_product_stock(6)

    def test_transfer_both(self):
        self.submit_xml_form(transfer_both)
        self.check_product_stock(6, self.first_spp)
        self.check_product_stock(14, self.second_spp)

    def test_transfer_neither(self):
        # TODO this one should error
        # self.submit_xml_form(transfer_neither)
        pass

    def test_balance_first_doc_order(self):
        self.submit_xml_form(balance_first)
        self.check_product_stock(73)

    def test_transfer_first_doc_order(self):
        self.submit_xml_form(transfer_first)
        self.check_product_stock(35)
