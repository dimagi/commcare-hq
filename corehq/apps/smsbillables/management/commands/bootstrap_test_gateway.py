from decimal import Decimal
import logging

from django.conf import settings
from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.messaging.smsbackends.test.models import TestSMSBackend
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


logger = logging.getLogger('accounting')


def bootstrap_test_gateway(apps):
    default_currency, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code=settings.DEFAULT_CURRENCY)
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        TestSMSBackend.get_api_id(),
        INCOMING,
        Decimal('0.0'),
        currency=default_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        TestSMSBackend.get_api_id(),
        OUTGOING,
        Decimal('0.0'),
        currency=default_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    logger.info("Updated Test gateway fees.")

bootstrap_test_gateway.__test__ = False


class Command(LabelCommand):
    help = "bootstrap Test SMS backend gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_test_gateway(None)
