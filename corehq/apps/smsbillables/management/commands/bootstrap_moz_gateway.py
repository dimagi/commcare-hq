from decimal import Decimal
import logging
from couchdbkit import ResourceNotFound

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.backend.http_api import HttpBackend
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


logger = logging.getLogger('accounting')


def bootstrap_moz_gateway(apps):
    mzn, _ = (apps.get_model('accounting', 'Currency') if apps else Currency).objects.get_or_create(code='MZN')
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        'SISLOG',
        INCOMING,
        Decimal('1.4625'),
        country_code='258',
        prefix='82',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        'SISLOG',
        INCOMING,
        Decimal('1.4625'),
        country_code='258',
        prefix='83',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        'SISLOG',
        INCOMING,
        Decimal('1.4625'),
        country_code='258',
        prefix='84',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        'SISLOG',
        INCOMING,
        Decimal('0.702'),
        country_code='258',
        prefix='86',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    SmsGatewayFee.create_new(
        'SISLOG',
        INCOMING,
        Decimal('0.702'),
        country_code='258',
        prefix='87',
        currency=mzn,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    backend_id = '7ddf3301c093b793c6020ebf755adb6f'
    try:
        backend = HttpBackend.get(backend_id)

        SmsGatewayFee.create_new(
            backend.get_api_id(),
            OUTGOING,
            Decimal('0.3627'),
            backend_instance=backend._id,
            country_code='258',
            prefix='82',
            currency=mzn,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )
        SmsGatewayFee.create_new(
            backend.get_api_id(),
            OUTGOING,
            Decimal('0.3627'),
            backend_instance=backend._id,
            country_code='258',
            prefix='83',
            currency=mzn,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )
        SmsGatewayFee.create_new(
            backend.get_api_id(),
            OUTGOING,
            Decimal('0.3627'),
            backend_instance=backend._id,
            country_code='258',
            prefix='84',
            currency=mzn,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )
        SmsGatewayFee.create_new(
            backend.get_api_id(),
            OUTGOING,
            Decimal('1.1232'),
            backend_instance=backend._id,
            country_code='258',
            prefix='86',
            currency=mzn,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )
        SmsGatewayFee.create_new(
            backend.get_api_id(),
            OUTGOING,
            Decimal('1.1232'),
            backend_instance=backend._id,
            country_code='258',
            prefix='87',
            currency=mzn,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )

        logger.info("Updated Moz gateway fees.")
    except ResourceNotFound:
        logger.error("[SMS-BILLING] Could not find HttpBackend %s - did not create outgoing Moz gateway fees."
                     " Please look into if this is on production, otherwise ignore." % backend_id)


class Command(LabelCommand):
    help = "bootstrap MOZ global SMS backend gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_moz_gateway(None)
