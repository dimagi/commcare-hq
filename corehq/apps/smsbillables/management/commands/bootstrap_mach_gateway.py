from itertools import islice

from django.core.management.base import BaseCommand

import openpyxl

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsbillables.models import (
    SmsGatewayFee,
    SmsGatewayFeeCriteria,
)
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.mach.models import SQLMachBackend


def bootstrap_mach_gateway(apps):
    currency_class = apps.get_model('accounting', 'Currency') if apps else Currency
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') \
        if apps else SmsGatewayFeeCriteria

    filename = 'corehq/apps/smsbillables/management/pricing_data/Syniverse_coverage_list_PREMIUM_Sept2019.xlsx'
    workbook = openpyxl.load_workbook(filename, read_only=True, data_only=True)
    table = workbook.worksheets[0]

    data = {}
    for row in islice(table.rows, 7, None):
        if row[6].value == 'yes':
            country_code = int(row[0].value)
            if not(country_code in data):
                data[country_code] = []
            subscribers = row[10].value.replace('.', '')
            try:
                data[country_code].append((row[9].value, int(subscribers)))
            except ValueError:
                log_smsbillables_info('Incomplete data for country code %d' % country_code)

    for country_code in data:
        total_subscribers = 0
        weighted_price = 0
        for price, subscribers in data[country_code]:
            total_subscribers += subscribers
            weighted_price += price * subscribers
        if total_subscribers == 0:
            continue
        weighted_price = weighted_price / total_subscribers
        SmsGatewayFee.create_new(
            SQLMachBackend.get_api_id(),
            OUTGOING,
            weighted_price,
            country_code=country_code,
            currency=currency_class.objects.get(code="EUR"),
            fee_class=sms_gateway_fee_class,
            criteria_class=sms_gateway_fee_criteria_class,
        )

    # Fee for invalid phonenumber
    SmsGatewayFee.create_new(
        SQLMachBackend.get_api_id(),
        OUTGOING,
        0.0225,
        country_code=None,
        currency=currency_class.objects.get(code="EUR"),
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    log_smsbillables_info("Updated MACH/Syniverse gateway fees.")


class Command(BaseCommand):
    help = "bootstrap MACH/Syniverse gateway fees"

    def handle(self, **options):
        bootstrap_mach_gateway(None)
