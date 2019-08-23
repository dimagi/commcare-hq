from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
import xlrd

from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.smsbillables.utils import log_smsbillables_info
from corehq.messaging.smsbackends.mach.models import SQLMachBackend
from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria


def bootstrap_mach_gateway(apps):
    currency_class = apps.get_model('accounting', 'Currency') if apps else Currency
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    workbook = xlrd.open_workbook('corehq/apps/smsbillables/management/pricing_data/Syniverse_coverage_list_PREMIUM.xls')
    table = workbook.sheet_by_index(0)

    data = {}
    try:
        row = 7
        while True:
            if table.cell_value(row, 6) == 'yes':
                country_code = int(table.cell_value(row, 0))
                if not(country_code in data):
                    data[country_code] = []
                subscribers = table.cell_value(row, 10).replace('.', '')
                try:
                    data[country_code].append(
                        (table.cell_value(row, 9), int(subscribers)))
                except ValueError:
                    log_smsbillables_info('Incomplete data for country code %d' % country_code)
            row += 1
    except IndexError:
        pass

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
