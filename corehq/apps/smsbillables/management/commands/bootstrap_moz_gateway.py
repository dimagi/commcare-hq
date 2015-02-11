from decimal import Decimal
import logging

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.backend.http_api import HttpBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee


logger = logging.getLogger('accounting')


class Command(LabelCommand):
    help = "bootstrap MOZ global SMS backend gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        mzn, _ = Currency.objects.get_or_create(code='MZN')

        SmsGatewayFee.create_new('SISLOG', INCOMING, Decimal('1.4625'), country_code='25882', currency=mzn)
        SmsGatewayFee.create_new('SISLOG', INCOMING, Decimal('1.4625'), country_code='25883', currency=mzn)
        SmsGatewayFee.create_new('SISLOG', INCOMING, Decimal('1.4625'), country_code='25884', currency=mzn)
        SmsGatewayFee.create_new('SISLOG', INCOMING, Decimal('0.702'), country_code='25886', currency=mzn)
        SmsGatewayFee.create_new('SISLOG', INCOMING, Decimal('0.702'), country_code='25887', currency=mzn)

        backend = HttpBackend.get('7ddf3301c093b793c6020ebf755adb6f')
        SmsGatewayFee.create_new(backend.get_api_id(), OUTGOING, Decimal('0.3627'),
            backend_instance=backend._id, country_code='25882', currency=mzn)
        SmsGatewayFee.create_new(backend.get_api_id(), OUTGOING, Decimal('0.3627'),
            backend_instance=backend._id, country_code='25883', currency=mzn)
        SmsGatewayFee.create_new(backend.get_api_id(), OUTGOING, Decimal('0.3627'),
            backend_instance=backend._id, country_code='25884', currency=mzn)
        SmsGatewayFee.create_new(backend.get_api_id(), OUTGOING, Decimal('1.1232'),
            backend_instance=backend._id, country_code='25886', currency=mzn)
        SmsGatewayFee.create_new(backend.get_api_id(), OUTGOING, Decimal('1.1232'),
            backend_instance=backend._id, country_code='25887', currency=mzn)
