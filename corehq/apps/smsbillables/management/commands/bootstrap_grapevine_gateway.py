from decimal import Decimal
import logging
from django.core.management.base import LabelCommand
from corehq.apps.accounting.models import Currency

from corehq.apps.grapevine.api import GrapevineBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee
from corehq.apps.smsbillables.utils import get_global_backends_by_class

logger = logging.getLogger('accounting')


class Command(LabelCommand):
    help = "bootstrap Grapevine gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        relevant_backends = get_global_backends_by_class(GrapevineBackend)
        currency = Currency.objects.get_or_create(code="ZAR")[0]

        # any incoming message
        SmsGatewayFee.create_new(
            GrapevineBackend.get_api_id(), INCOMING, Decimal('0.10'),
            currency=currency
        )
        logger.info("Updated Global Grapevine gateway fees.")

        # messages relevant to our Grapevine Backends
        for backend in relevant_backends:
            SmsGatewayFee.create_new(
                GrapevineBackend.get_api_id(), INCOMING, Decimal('0.10'),
                currency=currency, backend_instance=backend.get_id
            )
            SmsGatewayFee.create_new(
                GrapevineBackend.get_api_id(), OUTGOING, Decimal('0.22'),
                currency=currency, backend_instance=backend.get_id
            )

            logger.info("Updated Grapevine fees for backend %s" % backend.name)
