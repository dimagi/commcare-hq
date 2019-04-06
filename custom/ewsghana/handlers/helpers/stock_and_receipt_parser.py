from __future__ import absolute_import
from __future__ import unicode_literals
import re
from decimal import Decimal

from corehq.apps.commtrack.sms import StockAndReceiptParser, SMSError, const
from corehq.form_processor.parsers.ledgers import StockTransactionHelper
from custom.ewsghana.handlers import INVALID_PRODUCT_CODE


class ProductCodeException(Exception):
    pass


class EWSStockAndReceiptParser(StockAndReceiptParser):

    def __init__(self, domain, verified_contact, location=None):
        super(EWSStockAndReceiptParser, self).__init__(domain, verified_contact, location)
        self.bad_codes = set()

    def product_from_code(self, prod_code):
        try:
            return super(EWSStockAndReceiptParser, self).product_from_code(prod_code)
        except SMSError:
            return None

    def single_action_transactions(self, action, args):
        products = []
        for idx, arg in enumerate(args):
            if self.looks_like_prod_code(arg):
                product = self.product_from_code(arg)
                if product:
                    products.append(product)
                else:
                    if idx == 0:
                        raise ProductCodeException(INVALID_PRODUCT_CODE % arg)
                    self.bad_codes.add(arg)
            else:
                if not products:
                    continue
                if len(products) > 1:
                    raise SMSError('missing quantity for product "%s"' % products[-1].code)

                # NOTE also custom code here, must be formatted like 11.22
                if re.compile(r"^\d+\.\d+$").match(arg):
                    value = arg
                else:
                    raise SMSError('could not understand product quantity "%s"' % arg)

                for p in products:
                    # for EWS we have to do two transactions, one being a receipt
                    # and second being a transaction (that's reverse of the order
                    # the user provides them)
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location.location_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=const.StockActions.RECEIPTS,
                        quantity=Decimal(value.split('.')[1])
                    )
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location.location_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=const.StockActions.STOCKONHAND,
                        quantity=Decimal(value.split('.')[0])
                    )
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)
