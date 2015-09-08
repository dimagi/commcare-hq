from custom.ilsgateway.tanzania.handlers.generic_stock_report_handler import GenericStockReportHandler
from custom.ilsgateway.tanzania.handlers.ils_stock_report_parser import Formatter
from custom.ilsgateway.tanzania.reminders import STOCKOUT_CONFIRM


class StockoutFormatter(Formatter):

    def format(self, text):
        content = text.split(' ', 1)[1]
        products_codes = content.split()
        return u'soh {}'.format(u' 0 '.join(products_codes)) + ' 0'


class StockoutHandler(GenericStockReportHandler):
    formatter = StockoutFormatter

    def get_message(self, data):
        return STOCKOUT_CONFIRM % {
            'contact_name': self.verified_contact.owner.full_name,
            'product_names': self.msg.text.split(' ', 1)[1],
            'facility_name': self.sql_location.name
        }

    def on_success(self):
        pass
