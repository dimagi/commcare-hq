import settings
from django.core.management.base import BaseCommand
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import (
    SmsGatewayFee
)
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.amazon_pinpoint.models import PinpointBackend


def bootstrap_pinpoint_gateway(apps):
    default_currency, _ = apps.get_model(
        'accounting', 'Currency'
    ).objects.get_or_create(
        code=settings.DEFAULT_CURRENCY
    )

    for direction in [INCOMING, OUTGOING]:
        SmsGatewayFee.create_new(
            PinpointBackend.get_api_id(),
            direction,
            None,
            fee_class=apps.get_model('smsbillables', 'SmsGatewayFee'),
            criteria_class=apps.get_model('smsbillables', 'SmsGatewayFeeCriteria'),
            currency=default_currency,
        )

    log_smsbillables_info("Updated Pinpoint gateway fees.")


class Command(BaseCommand):
    help = "bootstrap Pinpoint gateway fees"

    def handle(self, **options):
        bootstrap_pinpoint_gateway(None)
