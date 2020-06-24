import settings
from django.core.management.base import BaseCommand
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import (
    SmsGatewayFee
)
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend


def bootstrap_twilio_gateway(apps):
    default_currency, _ = apps.get_model(
        'accounting', 'Currency'
    ).objects.get_or_create(
        code=settings.DEFAULT_CURRENCY
    )

    for direction in [INCOMING, OUTGOING]:
        SmsGatewayFee.create_new(
            SQLTwilioBackend.get_api_id(),
            direction,
            None,
            fee_class=apps.get_model('smsbillables', 'SmsGatewayFee'),
            criteria_class=apps.get_model('smsbillables', 'SmsGatewayFeeCriteria'),
            currency=default_currency,
        )

    log_smsbillables_info("Updated Twilio gateway fees.")


class Command(BaseCommand):
    help = "bootstrap Twilio gateway fees"

    def handle(self, **options):
        bootstrap_twilio_gateway(None)
