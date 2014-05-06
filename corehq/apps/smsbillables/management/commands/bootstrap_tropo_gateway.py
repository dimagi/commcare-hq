import logging
from django.core.management.base import LabelCommand

from corehq.apps.tropo.api import TropoBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee

logger = logging.getLogger('accounting')


class Command(LabelCommand):
    help = "bootstrap Tropo gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        SmsGatewayFee.create_new(TropoBackend.get_api_id(), INCOMING, 0.01)

        rates_csv = open('corehq/apps/smsbillables/management/'
                         'pricing_data/tropo_international_rates_2013-12-19.csv', 'r')
        for line in rates_csv.readlines():
            data = line.split(',')
            if data[1] == 'Fixed Line' and data[4] != '\n':
                SmsGatewayFee.create_new(TropoBackend.get_api_id(),
                                         OUTGOING,
                                         float(data[4].rstrip()),
                                         country_code=int(data[2]))
        rates_csv.close()

        # Fee for invalid phonenumber
        SmsGatewayFee.create_new(TropoBackend.get_api_id(), OUTGOING, 0.01, country_code=None)

        logger.info("Updated Tropo gateway fees.")
