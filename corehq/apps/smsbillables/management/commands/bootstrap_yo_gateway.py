from __future__ import absolute_import
from decimal import Decimal

from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.yo.models import SQLYoBackend


def bootstrap_yo_gateway(apps):
    ugx, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code='UGX')
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        SQLYoBackend.get_api_id(),
        INCOMING,
        Decimal('110.0'),
        currency=ugx,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        SQLYoBackend.get_api_id(),
        OUTGOING,
        Decimal('55.0'),
        currency=ugx,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    log_smsbillables_info("Updated Yo gateway fees.")


class Command(BaseCommand):
    help = "bootstrap Yo global SMS backend gateway fees"

    def handle(self, **options):
        bootstrap_yo_gateway(None)
