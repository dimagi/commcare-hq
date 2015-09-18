from decimal import Decimal
import logging
from django.core.management.base import LabelCommand
from corehq.apps.accounting.models import Currency

from corehq.apps.grapevine.api import GrapevineBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria

logger = logging.getLogger('accounting')


def bootstrap_grapevine_gateway_update(apps):
    currency_class = apps.get_model('accounting', 'Currency') if apps else Currency
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    currency = currency_class.objects.get_or_create(code="ZAR")[0]

    # Incoming message to South Africa
    SmsGatewayFee.create_new(
        GrapevineBackend.get_api_id(), INCOMING, Decimal('0.65'),
        country_code='27',
        currency=currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    # Outgoing message from South Africa
    SmsGatewayFee.create_new(
        GrapevineBackend.get_api_id(), OUTGOING, Decimal('0.22'),
        country_code='27',
        currency=currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    # Explicitly include Lesotho fees for pricing table UI.
    # Incoming message to Lesotho
    SmsGatewayFee.create_new(
        GrapevineBackend.get_api_id(), INCOMING, Decimal('0.90'),
        country_code='266',
        currency=currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    # Outgoing message from Lesotho
    SmsGatewayFee.create_new(
        GrapevineBackend.get_api_id(), OUTGOING, Decimal('0.90'),
        country_code='266',
        currency=currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    # Incoming message to arbitrary country
    SmsGatewayFee.create_new(
        GrapevineBackend.get_api_id(), INCOMING, Decimal('0.90'),
        currency=currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    # Outgoing message from arbitrary country
    SmsGatewayFee.create_new(
        GrapevineBackend.get_api_id(), OUTGOING, Decimal('0.90'),
        currency=currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    logger.info("Updated Global Grapevine gateway fees.")


class Command(LabelCommand):
    help = "update Grapevine gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_grapevine_gateway_update(None)
