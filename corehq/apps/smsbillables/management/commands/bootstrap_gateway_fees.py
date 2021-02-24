import re

import settings
from django.core.management.base import BaseCommand, CommandError
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.sms.util import get_sms_backend_classes
from corehq.apps.accounting.models import Currency
from corehq.apps.smsbillables.models import (
    SmsGatewayFee,
    SmsGatewayFeeCriteria
)
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.infobip.models import InfobipBackend
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.messaging.smsbackends.amazon_pinpoint.models import PinpointBackend


def bootstrap_infobip_gateway(apps):
    _bootstrap_gateway(apps, InfobipBackend)


def bootstrap_twilio_gateway(apps):
    _bootstrap_gateway(apps, SQLTwilioBackend)


def bootstrap_pinpoint_gateway(apps):
    _bootstrap_gateway(apps, PinpointBackend)


def _bootstrap_gateway(apps, backend, amount=None, country_code=None):
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee')\
        if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria')\
        if apps else SmsGatewayFeeCriteria
    default_currency, _ = (apps.get_model('accounting', 'Currency') if apps else Currency)\
        .objects.get_or_create(code=settings.DEFAULT_CURRENCY)

    for direction in [INCOMING, OUTGOING]:
        SmsGatewayFee.create_new(
            backend.get_api_id(),
            direction,
            amount,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
            currency=default_currency,
            country_code=country_code,
        )

    log_smsbillables_info(backend.get_api_id() + " - Updated gateway fees.")


class Command(BaseCommand):
    help = "bootstrap gateway fees for the given gateway API id (e.g. TWILIO)"

    def add_arguments(self, parser):
        parser.add_argument('gateway_api_id')
        parser.add_argument('--amount', help='The amount for inbound/outbound messages. Default is None.')
        parser.add_argument('--country', help='The country code used for messages. Default is None.')

    def handle(self, gateway_api_id, **kwargs):
        backend_class = get_sms_backend_classes()[gateway_api_id]
        amount = kwargs['amount']
        country = kwargs['country']

        decimal_pattern = re.compile("[0-9.]+")
        if amount is not None and decimal_pattern.fullmatch(amount) is None:
            raise CommandError('the amount option must be a number')

        number_pattern = re.compile("[0-9]+")
        if country is not None and number_pattern.fullmatch(country) is None:
            raise CommandError('the country option must be a whole number')

        _bootstrap_gateway(None, backend_class, amount, country)
