import logging
import os
import re
import xlrd

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria
from corehq.apps.unicel.api import UnicelBackend

logger = logging.getLogger('accounting')

FEE_COLUMN = 1
COUNTRY_CODES_COLUMN = 3


def bootstrap_unicel_outbound(orm):
    currency = (orm['accounting.Currency'] if orm else Currency).objects.get(code="INR")
    sms_gateway_fee_class = orm['smsbillables.SmsGatewayFee'] if orm else SmsGatewayFee
    sms_gateway_fee_criteria_class = orm['smsbillables.SmsGatewayFeeCriteria'] if orm else SmsGatewayFeeCriteria

    filename = (
        os.getcwd()
        + '/corehq/apps/smsbillables/management/pricing_data/Unicel-outgoing-codes.xls'
    )
    workbook = xlrd.open_workbook(filename)
    table = workbook.sheet_by_index(0)

    def get_codes(codes):
        if type(codes) is float:
            return [int(codes)]
        codes = codes.replace(' ', '').replace(u'\xa0', '').replace('+', '')
        # http://stackoverflow.com/questions/2403122/regular-expression-to-extract-text-between-square-brackets
        codes = re.sub(r'\[(.*?)\]', '', codes)
        return [int(code) for code in codes.split(',')]

    # Populate country-specific outgoing fees
    try:
        row = 1
        while True:
            fee = table.cell_value(row, FEE_COLUMN)
            country_codes = get_codes(table.cell_value(row, COUNTRY_CODES_COLUMN))
            for country_code in country_codes:
                SmsGatewayFee.create_new(
                    UnicelBackend.get_api_id(),
                    OUTGOING,
                    fee,
                    country_code=country_code,
                    currency=currency,
                    fee_class=sms_gateway_fee_class,
                    criteria_class=sms_gateway_fee_criteria_class,
                )
            row += 1
    except IndexError:
        pass

    # Remove existing non-country specific outgoing fees
    while True:
        old_outgoing_fee_criteria = SmsGatewayFeeCriteria.get_most_specific(
            UnicelBackend.get_api_id(),
            OUTGOING,
        )
        if old_outgoing_fee_criteria is None:
            break

        SmsGatewayFee.objects.filter(criteria=old_outgoing_fee_criteria).delete()
        old_outgoing_fee_criteria.delete()

    logger.info('Corrected outgoing gateway fees for Unicel')


class Command(LabelCommand):
    help = "Correct outgoing gateway fees for Unicel"
    args = ""
    label = ""

    def handle(self, *labels, **options):
        bootstrap_unicel_outbound(None)
