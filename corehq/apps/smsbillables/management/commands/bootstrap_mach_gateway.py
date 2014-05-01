import logging
import xlrd

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.mach.api import MachBackend
from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee

logger = logging.getLogger('accounting')


class Command(LabelCommand):
    help = "bootstrap MACH/Syniverse gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        workbook = xlrd.open_workbook('corehq/apps/smsbillables/management/'
                                      'commands/pricing_data/Syniverse_coverage_list_DIAMONDplus.xls')
        table = workbook.sheet_by_index(0)

        data = {}
        try:
            row = 7
            while True:
                if table.cell_value(row, 6) == 'yes':
                    country_code = int(table.cell_value(row, 0))
                    if not(country_code in data):
                        data[country_code] = []
                    subscribers = table.cell_value(row,10).replace('.', '')
                    try:
                        data[country_code].append(
                            (table.cell_value(row, 9), int(subscribers)))
                    except ValueError:
                        logger.info('Incomplete data for country code %d' % country_code)
                row += 1
        except IndexError:
            pass

        for country_code in data:
            total_subscribers = 0
            weighted_price = 0
            for price, subscribers in data[country_code]:
                total_subscribers += subscribers
                weighted_price += price * subscribers
            weighted_price = weighted_price / total_subscribers
            SmsGatewayFee.create_new(MachBackend.get_api_id(), OUTGOING, weighted_price,
                                     country_code=country_code, currency=Currency.objects.get(code="EUR"))

        # Fee for invalid phonenumber
        SmsGatewayFee.create_new(MachBackend.get_api_id(), OUTGOING, 0.0225,
                                 country_code=None, currency=Currency.objects.get(code="EUR"))

        logger.info("Updated MACH/Syniverse gateway fees.")
