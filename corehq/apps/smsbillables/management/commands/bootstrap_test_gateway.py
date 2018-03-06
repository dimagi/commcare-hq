from __future__ import absolute_import
from __future__ import unicode_literals
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.test.models import SQLTestSMSBackend
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


def bootstrap_test_gateway(apps):
    default_currency, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code=settings.DEFAULT_CURRENCY)
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        SQLTestSMSBackend.get_api_id(),
        INCOMING,
        Decimal('0.0'),
        currency=default_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        SQLTestSMSBackend.get_api_id(),
        OUTGOING,
        Decimal('0.0'),
        currency=default_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    log_smsbillables_info("Updated Test gateway fees.")

bootstrap_test_gateway.__test__ = False


class Command(BaseCommand):
    help = "bootstrap Test SMS backend gateway fees"

    def handle(self, **options):
        bootstrap_test_gateway(None)
