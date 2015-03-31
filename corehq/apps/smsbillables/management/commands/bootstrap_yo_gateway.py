from decimal import Decimal
import logging

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


logger = logging.getLogger('accounting')


def bootstrap_yo_gateway(orm):
    ugx, _ = (orm['accounting.Currency'] if orm else Currency).objects.get_or_create(code='UGX')
    sms_gateway_fee_class = orm['smsbillables.SmsGatewayFee'] if orm else SmsGatewayFee
    sms_gateway_fee_criteria_class = orm['smsbillables.SmsGatewayFeeCriteria'] if orm else SmsGatewayFeeCriteria

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
