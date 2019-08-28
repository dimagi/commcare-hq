from decimal import Decimal

from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import (
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
)
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend


def add_moz_zero_charge(apps):
    mzn, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code='MZN')
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        INCOMING,
        Decimal('0'),
        country_code=None,
        prefix='',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        OUTGOING,
        Decimal('0'),
        country_code=None,
        prefix='',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    log_smsbillables_info("Updated Moz gateway default fees.")


class Command(BaseCommand):
    help = "bootstrap MOZ global SMS backend gateway default fees"

    def handle(self, **options):
        add_moz_zero_charge(None)
