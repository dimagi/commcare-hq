import logging
from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria
from commcarehq.messaging.smsbackends.unicel.api import UnicelBackend

logger = logging.getLogger('accounting')


def bootstrap_unicel_gateway(orm):
    currency = (orm['accounting.Currency'] if orm else Currency).objects.get(code="INR")
    sms_gateway_fee_class = orm['smsbillables.SmsGatewayFee'] if orm else SmsGatewayFee
    sms_gateway_fee_criteria_class = orm['smsbillables.SmsGatewayFeeCriteria'] if orm else SmsGatewayFeeCriteria

    SmsGatewayFee.create_new(UnicelBackend.get_api_id(), INCOMING, 0.50,
                             currency=currency,
                             fee_class=sms_gateway_fee_class,
                             criteria_class=sms_gateway_fee_criteria_class)
    SmsGatewayFee.create_new(UnicelBackend.get_api_id(), OUTGOING, 0.50,
                             currency=currency,
                             fee_class=sms_gateway_fee_class,
                             criteria_class=sms_gateway_fee_criteria_class)
    logger.info("Updated Unicel gateway fees.")


class Command(LabelCommand):
    help = "bootstrap Unicel gateway fees"
    args = ""
    label = ""

    def handle(self, *labels, **options):
        bootstrap_unicel_gateway(None)
