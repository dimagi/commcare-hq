from decimal import Decimal

from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import INCOMING, OUTGOING
from corehq.apps.smsbillables.models import (
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
)
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.grapevine.models import SQLGrapevineBackend


def bootstrap_grapevine_gateway(apps):
    currency_class = apps.get_model('accounting', 'Currency') if apps else Currency
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    relevant_backends = SQLGrapevineBackend.get_global_backends_for_this_class(SQLGrapevineBackend.SMS)
    currency = currency_class.objects.get_or_create(code="ZAR")[0]

    # any incoming message
    SmsGatewayFee.create_new(
        SQLGrapevineBackend.get_api_id(), INCOMING, Decimal('0.10'),
        currency=currency,
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )
    log_smsbillables_info("Updated Global Grapevine gateway fees.")

    # messages relevant to our Grapevine Backends
    for backend in relevant_backends:
        SmsGatewayFee.create_new(
            SQLGrapevineBackend.get_api_id(), INCOMING, Decimal('0.10'),
            currency=currency, backend_instance=backend.couch_id,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )
        SmsGatewayFee.create_new(
            SQLGrapevineBackend.get_api_id(), OUTGOING, Decimal('0.22'),
            currency=currency, backend_instance=backend.couch_id,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )

        log_smsbillables_info("Updated Grapevine fees for backend %s" % backend.name)


class Command(BaseCommand):
    help = "bootstrap Grapevine gateway fees"

    def handle(self, **options):
        bootstrap_grapevine_gateway(None)
