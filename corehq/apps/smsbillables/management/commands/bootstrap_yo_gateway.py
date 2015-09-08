from decimal import Decimal
import logging

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


logger = logging.getLogger('accounting')


def bootstrap_yo_gateway(apps):
    ugx, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code='UGX')
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        'YO',
        INCOMING,
        Decimal('110.0'),
        currency=ugx,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        'HTTP',
        OUTGOING,
        Decimal('55.0'),
        backend_instance='95a4f0929cddb966e292e70a634da716',
        currency=ugx,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    logger.info("Updated Yo gateway fees.")


class Command(LabelCommand):
    help = "bootstrap Yo global SMS backend gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_yo_gateway(None)
