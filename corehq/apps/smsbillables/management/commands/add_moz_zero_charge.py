from decimal import Decimal
import logging
from couchdbkit import ResourceNotFound

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


logger = logging.getLogger('accounting')


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

    logger.info("Updated Moz gateway default fees.")


class Command(LabelCommand):
    help = "bootstrap MOZ global SMS backend gateway default fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        add_moz_zero_charge(None)
