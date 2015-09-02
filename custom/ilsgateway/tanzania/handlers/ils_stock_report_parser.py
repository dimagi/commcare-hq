from corehq.apps.commtrack.sms import StockReportParser
from custom.ilsgateway import LOGISTICS_PRODUCT_ALIASES


class Formatter(object):

    def format(self, text):
        raise NotImplemented()


class ILSStockReportParser(StockReportParser):

    _formatterBridge = None

    def __init__(self, domain, v, formatter=None):
        super(ILSStockReportParser, self).__init__(domain, v)
        self._formatterBridge = formatter

    def parse(self, text):
        text = self._formatterBridge.format(text)
        return super(ILSStockReportParser, self).parse(text)

    def product_from_code(self, prod_code):
        if prod_code.lower() in LOGISTICS_PRODUCT_ALIASES:
            prod_code = LOGISTICS_PRODUCT_ALIASES[prod_code.lower()]
        return super(ILSStockReportParser, self).product_from_code(prod_code)
