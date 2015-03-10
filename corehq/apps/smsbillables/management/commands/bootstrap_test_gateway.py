from decimal import Decimal
import logging

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.sms.test_backend import TestSMSBackend
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


logger = logging.getLogger('accounting')


def bootstrap_test_gateway(orm):
    default_currency = (orm['accounting.Currency'] if orm else Currency).get_default()
    sms_gateway_fee_class = orm['smsbillables.SmsGatewayFee'] if orm else SmsGatewayFee
    sms_gateway_fee_criteria_class = orm['smsbillables.SmsGatewayFeeCriteria'] if orm else SmsGatewayFeeCriteria

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


class Command(LabelCommand):
    help = "bootstrap Test SMS backend gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_test_gateway(None)
