from decimal import Decimal
import logging

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria
from commcarehq.messaging.smsbackends.telerivet.models import TelerivetBackend


logger = logging.getLogger('accounting')


def bootstrap_telerivet_gateway(orm):
    default_currency = (orm['accounting.Currency'] if orm else Currency).get_default()
    sms_gateway_fee_class = orm['smsbillables.SmsGatewayFee'] if orm else SmsGatewayFee
    sms_gateway_fee_criteria_class = orm['smsbillables.SmsGatewayFeeCriteria'] if orm else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(
        TelerivetBackend.get_api_id(),
        INCOMING,
        Decimal('0.0'),
        currency=default_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    SmsGatewayFee.create_new(
        TelerivetBackend.get_api_id(),
        OUTGOING,
        Decimal('0.0'),
        currency=default_currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    logger.info("Updated Telerivet gateway fees.")


class Command(LabelCommand):
    help = "bootstrap Telerivet SMS backend gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_telerivet_gateway(None)
