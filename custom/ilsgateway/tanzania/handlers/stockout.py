from __future__ import absolute_import
from __future__ import unicode_literals

import six

from corehq.util.translation import localize
from custom.ilsgateway.tanzania.exceptions import InvalidProductCodeException
from custom.ilsgateway.tanzania.handlers.generic_stock_report_handler import GenericStockReportHandler
from custom.ilsgateway.tanzania.handlers.ils_stock_report_parser import Formatter
from custom.ilsgateway.tanzania.reminders import STOCKOUT_CONFIRM, INVALID_PRODUCT_CODE, STOCKOUT_HELP


class StockoutFormatter(Formatter):

    def format(self, text):
        content = text.split(' ', 1)[1]
        products_codes = content.split()
        return 'soh {}'.format(' 0 '.join(products_codes)) + ' 0'


class StockoutHandler(GenericStockReportHandler):
    formatter = StockoutFormatter

    def help(self):
        self.respond(STOCKOUT_HELP)
        return True

    def get_message(self, data):
        with localize(self.user.get_language_code()):
            return STOCKOUT_CONFIRM % {
                'contact_name': self.verified_contact.owner.full_name,
                'product_names': self.msg.text.split(' ', 1)[1],
                'facility_name': self.sql_location.name
            }

    def on_success(self):
        pass

    def on_error(self, data):
        for error in data['errors']:
            if isinstance(error, InvalidProductCodeException):
                self.respond(INVALID_PRODUCT_CODE, product_code=six.text_type(error))
