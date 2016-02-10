import logging

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.apps.sms.models import INCOMING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria

logger = logging.getLogger('accounting')


def bootstrap_twilio_gateway_incoming(apps):
    currency_class = apps.get_model('accounting', 'Currency') if apps else Currency
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    # https://www.twilio.com/sms/pricing/us
    SmsGatewayFee.create_new(
        SQLTwilioBackend.get_api_id(),
        INCOMING,
        0.0075,
        country_code=None,
        currency=currency_class.objects.get(code="USD"),
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    logger.info("Updated INCOMING Twilio gateway fees.")


class Command(LabelCommand):
    help = "bootstrap incoming Twilio gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_twilio_gateway_incoming(None)
