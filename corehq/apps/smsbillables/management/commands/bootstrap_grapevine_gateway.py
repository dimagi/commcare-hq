import logging
from django.core.management.base import LabelCommand

from corehq.apps.grapevine.api import GrapevineBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee

logger = logging.getLogger('accounting')


class Command(LabelCommand):
    help = "bootstrap Grapevine gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        SmsGatewayFee.create_new(GrapevineBackend.get_api_id(), INCOMING, 0.02)
        SmsGatewayFee.create_new(GrapevineBackend.get_api_id(), OUTGOING, 0.02)
        logger.info("Updated Grapevine gateway fees.")
