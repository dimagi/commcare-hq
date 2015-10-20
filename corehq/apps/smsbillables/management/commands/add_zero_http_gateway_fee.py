from decimal import Decimal
import logging
from couchdbkit import ResourceNotFound

from django.apps import apps
from django.conf import settings
from django.core.management.base import LabelCommand

from corehq.apps.smsbillables.models import SmsGatewayFee
from corehq.messaging.smsbackends.http.api import HttpBackend


logger = logging.getLogger('accounting')


def add_zero_http_gateway_fee(backend_id, direction, django_apps):
    currency, _ = (
        django_apps.get_model('accounting', 'Currency')
    ).objects.get_or_create(code=settings.DEFAULT_CURRENCY)
    sms_gateway_fee_class = (
        django_apps.get_model('smsbillables', 'SmsGatewayFee')
    )
    sms_gateway_fee_criteria_class = (
        django_apps.get_model('smsbillables', 'SmsGatewayFeeCriteria')
    )

    try:
        backend = HttpBackend.get(backend_id)

        SmsGatewayFee.create_new(
            backend.get_api_id(),
            direction,
            Decimal('0'),
            backend_instance=backend._id,
            country_code=None,
            prefix='',
            currency=currency,
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )

        logger.info("Updated gateway fee for HttpBackend %s" % backend_id)
    except ResourceNotFound:
        logger.error("[SMS-BILLING] Could not find HttpBackend %s - did not create gateway fees."
                     " Please look into if this is on production, otherwise ignore." % backend_id)


class Command(LabelCommand):
    help = "bootstrap default zero gateway fee for given HttpBackend and direction"
    args = "backend_id direction"
    label = ""

    def handle(self, backend_id, direction, *args, **options):
        add_zero_http_gateway_fee(backend_id, direction, apps)
