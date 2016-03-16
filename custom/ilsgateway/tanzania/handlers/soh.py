from datetime import datetime
from re import findall
from strop import maketrans
from custom.ilsgateway.tanzania.handlers.generic_stock_report_handler import GenericStockReportHandler
from custom.ilsgateway.tanzania.handlers.ils_stock_report_parser import Formatter

from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues, SupplyPointStatus
from custom.ilsgateway.tanzania.reminders import SOH_HELP_MESSAGE, SOH_CONFIRM, SOH_BAD_FORMAT


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

    def _cleanup(s):
        return unicode(s).encode('utf-8')

    return [
        (x[0], int(x[1].translate(maketrans("lLO", "110"))))
        for x in findall(
            "\s*(?P<code>[A-Za-z]{%(minchars)d,%(maxchars)d})\s*"
            "(?P<quantity>[+-]?[ ]*[0-9%(numeric_letters)s]+)\s*" %
            {
                "minchars": 2,
                "maxchars": 4,
                "numeric_letters": "lLO"
            }, _cleanup(val))
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

    def get_message(self, data):
        return SOH_CONFIRM

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
