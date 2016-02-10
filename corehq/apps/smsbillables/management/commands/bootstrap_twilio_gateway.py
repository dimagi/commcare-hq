import csv
import logging
import xlrd

from django.core.management.base import LabelCommand

from corehq.apps.accounting.models import Currency
from corehq.messaging.smsbackends.twilio.models import SQLTwilioBackend
from corehq.apps.sms.models import OUTGOING
from corehq.apps.smsbillables.models import SmsGatewayFee, SmsGatewayFeeCriteria

logger = logging.getLogger('accounting')


def bootstrap_twilio_gateway(apps, twilio_rates_filename):
    currency_class = apps.get_model('accounting', 'Currency') if apps else Currency
    sms_gateway_fee_class = apps.get_model('smsbillables', 'SmsGatewayFee') if apps else SmsGatewayFee
    sms_gateway_fee_criteria_class = apps.get_model('smsbillables', 'SmsGatewayFeeCriteria') if apps else SmsGatewayFeeCriteria

    # iso -> provider -> rate
    def get_twilio_data():
        twilio_file = open(twilio_rates_filename)
        twilio_csv = csv.reader(twilio_file.read().splitlines())
        twilio_data = {}
        skip = 0
        for row in twilio_csv:
            if skip < 4:
                skip += 1
                continue
            else:
                try:
                    iso = row[0].lower()
                    provider = row[2].split('-')[1].lower().replace(' ', '')
                    rate = float(row[3])
                    if not(iso in twilio_data):
                        twilio_data[iso] = {}
                    twilio_data[iso][provider] = rate
                except IndexError:
                    logger.info("Twilio index error %s:" % row)
        twilio_file.close()
        return twilio_data

    # iso -> provider -> (country code, number of subscribers)
    def get_mach_data():
        mach_workbook = xlrd.open_workbook('corehq/apps/smsbillables/management/'
                                           'commands/pricing_data/Syniverse_coverage_list_DIAMONDplus.xls')
        mach_table = mach_workbook.sheet_by_index(0)
        mach_data = {}
        try:
            row = 7
            while True:
                country_code = int(mach_table.cell_value(row, 0))
                iso = mach_table.cell_value(row, 1)
                network = mach_table.cell_value(row, 5).lower().replace(' ', '')
                subscribers = 0
                try:
                    subscribers = int(mach_table.cell_value(row, 10).replace('.', ''))
                except ValueError:
                    logger.info("Incomplete subscriber data for country code %d" % country_code)
                if not(iso in mach_data):
                    mach_data[iso] = {}
                mach_data[iso][network] = (country_code, subscribers)
                row += 1
        except IndexError:
            pass
        return mach_data

    twilio_data = get_twilio_data()
    mach_data = get_mach_data()

    for iso in twilio_data:
        if iso in mach_data:
            weighted_price = 0
            total_subscriptions = 0
            country_code = None
            calculate_other = False
            for twilio_provider in twilio_data[iso]:
                if twilio_provider == 'other':
                    calculate_other = True
                else:
                    for mach_provider in mach_data[iso]:
                        try:
                            if twilio_provider in mach_provider:
                                country_code, subscriptions = mach_data[iso][mach_provider]
                                weighted_price += twilio_data[iso][twilio_provider] * subscriptions
                                total_subscriptions += subscriptions
                                mach_data[iso][mach_provider] = country_code, 0
                                break
                        except UnicodeDecodeError:
                            pass
            if calculate_other:
                other_rate_twilio = twilio_data[iso]['other']
                for _, subscriptions in mach_data[iso].values():
                    weighted_price += other_rate_twilio * subscriptions
                    total_subscriptions += subscriptions
            if country_code is not None:
                weighted_price = weighted_price / total_subscriptions
                SmsGatewayFee.create_new(
                    SQLTwilioBackend.get_api_id(),
                    OUTGOING,
                    weighted_price,
                    country_code=country_code,
                    currency=currency_class.objects.get(code="USD"),
                    fee_class=sms_gateway_fee_class,
                    criteria_class=sms_gateway_fee_criteria_class,
                )
        else:
            logger.info("%s not in mach_data" % iso)

    # https://www.twilio.com/help/faq/sms/will-i-be-charged-if-twilio-encounters-an-error-when-sending-an-sms
    SmsGatewayFee.create_new(
        SQLTwilioBackend.get_api_id(),
        OUTGOING,
        0.00,
        country_code=None,
        currency=currency_class.objects.get(code="USD"),
        fee_class=sms_gateway_fee_class,
        criteria_class=sms_gateway_fee_criteria_class,
    )

    logger.info("Updated Twilio gateway fees.")


class Command(LabelCommand):
    help = "bootstrap Twilio gateway fees"
    args = ""
    label = ""

    def handle(self, *args, **options):
        bootstrap_twilio_gateway(None)
