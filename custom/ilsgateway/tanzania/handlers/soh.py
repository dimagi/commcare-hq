from __future__ import absolute_import
from __future__ import unicode_literals
from datetime import datetime
from re import findall

from custom.ilsgateway.slab.messages import REMINDER_TRANS, SOH_OVERSTOCKED
from custom.ilsgateway.tanzania.handlers.generic_stock_report_handler import GenericStockReportHandler
from custom.ilsgateway.tanzania.handlers.ils_stock_report_parser import Formatter

from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues, SupplyPointStatus, SLABConfig
from custom.ilsgateway.tanzania.reminders import SOH_HELP_MESSAGE, SOH_CONFIRM, SOH_BAD_FORMAT
from custom.ilsgateway.slab.utils import overstocked_products
import six


def parse_report(val):
    """
    PORTED FROM LOGISTICS:
    Takes a product report string, such as "zi 10 co 20 la 30", and parses it into a list of tuples
    of (code, quantity):

    >>> parse_report("zi 10 co 20 la 30")
    [('zi', 10), ('co', 20), ('la', 30)]

    Properly handles arbitrary whitespace:

    >>> parse_report("zi10 co20 la30")
    [('zi', 10), ('co', 20), ('la', 30)]

    Properly deals with Os being used for 0s:

    >>> parse_report("zi1O co2O la3O")
    [('zi', 10), ('co', 20), ('la', 30)]

    Properly handles extra spam in the string:

    >>> parse_report("randomextradata zi1O co2O la3O randomextradata")
    [('zi', 10), ('co', 20), ('la', 30)]
    """

    if six.PY3:
        maketrans = str.maketrans
        if isinstance(val, bytes):
            val = val.decode('utf-8')

        return [
            (x[0], int(x[1].replace(' ', '').translate(maketrans("lLO", "110"))))
            for x in findall(
                "\s*(?P<code>[A-Za-z]{%(minchars)d,%(maxchars)d})\s*"
                "(?P<quantity>[+-]?[ ]*[0-9%(numeric_letters)s]+)\s*" % {
                    "minchars": 2,
                    "maxchars": 4,
                    "numeric_letters": "lLO"
                }, val)
        ]
    else:
        from strop import maketrans
        if isinstance(val, six.text_type):
            val = val.encode('utf-8')

        return [
            (x[0], int(x[1].translate(maketrans("lLO", "110"))))
            for x in findall(
                "\s*(?P<code>[A-Za-z]{%(minchars)d,%(maxchars)d})\s*"
                "(?P<quantity>[+-]?[ ]*[0-9%(numeric_letters)s]+)\s*" % {
                    "minchars": 2,
                    "maxchars": 4,
                    "numeric_letters": "lLO"
                }, val)
        ]


class SohFormatter(Formatter):

    def format(self, text):
        split_text = text.split(' ', 1)
        keyword = split_text[0].lower()
        content = ' '.join('{} {}'.format(code, amount) for code, amount in parse_report(split_text[1]))
        if keyword == 'hmk':
            text = 'soh ' + content
        return text


class SOHHandler(GenericStockReportHandler):

    formatter = SohFormatter

    def _is_pilot_location(self):
        try:
            slab_config = SLABConfig.objects.get(sql_location=self.sql_location)
            return slab_config.is_pilot
        except SLABConfig.DoesNotExist:
            return False

    def get_message(self, data):
        if not self._is_pilot_location():
            return SOH_CONFIRM
        else:
            overstocked_msg = ""
            products_msg = ""
            for product_code, stock_on_hand, six_month_consumption in overstocked_products(self.sql_location):
                overstocked_msg += "%s: %s " % (product_code, stock_on_hand)
                products_msg += "%s: %s " % (product_code, six_month_consumption)

            if overstocked_msg and products_msg:
                self.respond(
                    SOH_OVERSTOCKED, overstocked_list=overstocked_msg.strip(), products_list=products_msg.strip()
                )
            return REMINDER_TRANS

    def on_success(self):
        SupplyPointStatus.objects.create(location_id=self.location_id,
                                         status_type=SupplyPointStatusTypes.SOH_FACILITY,
                                         status_value=SupplyPointStatusValues.SUBMITTED,
                                         status_date=datetime.utcnow())
        SupplyPointStatus.objects.create(location_id=self.location_id,
                                         status_type=SupplyPointStatusTypes.LOSS_ADJUSTMENT_FACILITY,
                                         status_value=SupplyPointStatusValues.REMINDER_SENT,
                                         status_date=datetime.utcnow())

    def on_error(self, data):
        self.respond(SOH_BAD_FORMAT)

    def help(self):
        self.respond(SOH_HELP_MESSAGE)
        return True
