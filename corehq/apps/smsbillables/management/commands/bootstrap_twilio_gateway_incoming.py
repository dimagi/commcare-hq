from __future__ import absolute_import
from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.apps.sms.models import INCOMING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


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

    log_smsbillables_info("Updated INCOMING Twilio gateway fees.")


class Command(BaseCommand):
    help = "bootstrap incoming Twilio gateway fees"

    def handle(self, **options):
        bootstrap_twilio_gateway_incoming(None)
