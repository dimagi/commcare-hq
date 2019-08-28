from decimal import Decimal
from django.core.management.base import BaseCommand
from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.apposit.models import SQLAppositBackend


def bootstrap_apposit_gateway(apps=None):
    usd_currency, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code="USD")
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        SQLAppositBackend.get_api_id(),
        INCOMING,
        Decimal('0.02'),
        currency=usd_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        SQLAppositBackend.get_api_id(),
        OUTGOING,
        Decimal('0.02'),
        currency=usd_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    log_smsbillables_info("Updated Apposit gateway fees.")


class Command(BaseCommand):
    help = "bootstrap Apposit backend gateway fees"

    def handle(self, **options):
        bootstrap_apposit_gateway()
