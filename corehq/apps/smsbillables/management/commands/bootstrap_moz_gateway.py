from __future__ import absolute_import
from decimal import Decimal

from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.sislog.models import SQLSislogBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


def bootstrap_moz_gateway(apps):
    mzn, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code='MZN')
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        INCOMING,
        Decimal('1.4625'),
        country_code='258',
        prefix='82',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        INCOMING,
        Decimal('1.4625'),
        country_code='258',
        prefix='83',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        INCOMING,
        Decimal('1.4625'),
        country_code='258',
        prefix='84',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        INCOMING,
        Decimal('0.702'),
        country_code='258',
        prefix='86',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        INCOMING,
        Decimal('0.702'),
        country_code='258',
        prefix='87',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        OUTGOING,
        Decimal('0.3627'),
        country_code='258',
        prefix='82',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        OUTGOING,
        Decimal('0.3627'),
        country_code='258',
        prefix='83',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        OUTGOING,
        Decimal('0.3627'),
        country_code='258',
        prefix='84',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        OUTGOING,
        Decimal('1.1232'),
        country_code='258',
        prefix='86',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        SQLSislogBackend.get_api_id(),
        OUTGOING,
        Decimal('1.1232'),
        country_code='258',
        prefix='87',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    log_smsbillables_info("Updated Moz gateway fees.")


class Command(BaseCommand):
    help = "bootstrap MOZ global SMS backend gateway fees"

    def handle(self, **options):
        bootstrap_moz_gateway(None)
