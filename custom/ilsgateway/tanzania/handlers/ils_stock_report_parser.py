from corehq.apps.commtrack.models import StockTransactionHelper
from corehq.apps.commtrack.sms import StockReportParser, SMSError
from custom.ilsgateway import LOGISTICS_PRODUCT_ALIASES


class Formatter(object):

    def format(self, text):
        raise NotImplemented()


class ILSStockReportParser(StockReportParser):

    _formatterBridge = None

    def __init__(self, domain, v, formatter=None):
        super(ILSStockReportParser, self).__init__(domain, v)
        self._formatterBridge = formatter
        self.error = False

    def parse(self, text):
        text = self._formatterBridge.format(text)
        result = super(ILSStockReportParser, self).parse(text)
        result['error'] = self.error
        return result

    def product_from_code(self, prod_code):
        if prod_code.lower() in LOGISTICS_PRODUCT_ALIASES:
            prod_code = LOGISTICS_PRODUCT_ALIASES[prod_code.lower()]
        try:
            return super(ILSStockReportParser, self).product_from_code(prod_code)
        except SMSError:
            return

    def single_action_transactions(self, action, args):
        products = []
        for arg in args:
            if self.looks_like_prod_code(arg):
                product = self.product_from_code(arg)
                if product:
                    products.append(product)
                else:
                    self.error = True
            else:
                if not products:
                    continue
                if len(products) > 1:
                    raise SMSError('missing quantity for product "%s"' % products[-1].code)

                try:
                    value = int(arg)
                except:
                    raise SMSError('could not understand product quantity "%s"' % arg)

                for p in products:
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location['location'].get_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=action.action,
                        subaction=action.subaction,
                        quantity=value,
                    )
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)
