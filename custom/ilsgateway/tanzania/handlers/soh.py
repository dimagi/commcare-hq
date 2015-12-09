from datetime import datetime, timedelta
from re import findall
from strop import maketrans
from corehq.apps.commtrack.models import StockState
from corehq.apps.products.models import SQLProduct
from custom.ilsgateway.tanzania.handlers.generic_stock_report_handler import GenericStockReportHandler
from custom.ilsgateway.tanzania.handlers.ils_stock_report_parser import Formatter

from custom.ilsgateway.models import SupplyPointStatusTypes, SupplyPointStatusValues, SupplyPointStatus
from custom.ilsgateway.tanzania.reminders import SOH_HELP_MESSAGE, SOH_CONFIRM, SOH_PARTIAL_CONFIRM, SOH_BAD_FORMAT


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
            "\s*(?P<code>[A-Za-z]{%(minchars)d,%(maxchars)d})\s*(?P<quantity>[\-?0-9%(numeric_letters)s]+)\s*" %
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
        if data['error']:
            return SOH_BAD_FORMAT
        reported_earlier = StockState.objects.filter(
            case_id=self.sql_location.couch_location.linked_supply_point().get_id,
            last_modified_date__gte=datetime.utcnow() - timedelta(days=7)
        ).values_list('product_id', flat=True)
        expected_products = set(
            self.location_products.exclude(product_id__in=reported_earlier).values_list('product_id', flat=True)
        )

        reported_now = {
            tx.product_id
            for tx in data['transactions']
        }
        diff = expected_products - reported_now
        if diff:
            return SOH_PARTIAL_CONFIRM % {
                'contact_name': self.verified_contact.owner.full_name,
                'facility_name': self.sql_location.name,
                'product_list': ' '.join(
                    sorted([SQLProduct.objects.get(product_id=product_id).code for product_id in diff])
                )
            }
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

    def help(self):
        self.respond(SOH_HELP_MESSAGE)
        return True
