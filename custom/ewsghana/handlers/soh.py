from __future__ import absolute_import
from __future__ import unicode_literals
from collections import defaultdict

from django.conf import settings

from corehq.apps.commtrack.exceptions import NotAUserClassError, NoDefaultLocationException
from corehq.apps.commtrack.models import StockState
from corehq.apps.commtrack.sms import SMSError, process
from corehq.apps.domain.models import Domain
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.reminders.util import get_preferred_phone_number_for_recipient
from corehq.apps.users.models import CommCareUser
from custom.ewsghana.handlers import INVALID_MESSAGE, ASSISTANCE_MESSAGE,\
    MS_STOCKOUT, MS_RESOLVED_STOCKOUTS, NO_SUPPLY_POINT_MESSAGE
from casexml.apps.stock.const import SECTION_TYPE_STOCK
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.toggles import EWS_INVALID_REPORT_RESPONSE
from custom.ewsghana.handlers.keyword import KeywordHandler
from custom.ewsghana.handlers.helpers.formatter import EWSFormatter
from custom.ewsghana.handlers.helpers.stock_and_receipt_parser import EWSStockAndReceiptParser, \
    ProductCodeException
from custom.ewsghana.reminders import ERROR_MESSAGE, SOH_HELP_MESSAGE
from custom.ewsghana.tasks import send_soh_messages_task
from custom.ewsghana.utils import ProductsReportHelper, send_sms
from custom.ewsghana.alerts.alerts import SOHAlerts
from dimagi.utils.couch.database import iter_docs
import six
from six.moves import map


def get_transactions_by_product(transactions):
    result = defaultdict(list)
    for tx in transactions:
        result[tx.product_id].append(tx)
    return result


class SOHHandler(KeywordHandler):

    async_response = False

    def get_valid_reports(self, data):
        filtered_transactions = []
        excluded_products = []
        for product_id, transactions in six.iteritems(get_transactions_by_product(data['transactions'])):
            begin_soh = None
            end_soh = None
            receipt = 0
            for transaction in transactions:
                if begin_soh is None:
                    sql_location = SQLLocation.objects.get(location_id=transaction.location_id)
                    latest = StockTransaction.latest(
                        sql_location.supply_point_id,
                        SECTION_TYPE_STOCK,
                        transaction.product_id
                    )
                    begin_soh = 0
                    if latest:
                        begin_soh = float(latest.stock_on_hand)

                if transaction.action == 'receipts':
                    receipt += float(transaction.quantity)
                elif not end_soh:
                    end_soh = float(transaction.quantity)
            if end_soh > begin_soh + receipt:
                excluded_products.append(transaction.product_id)
            else:
                filtered_transactions.append(transaction)
        if excluded_products:
            message = ERROR_MESSAGE.format(products_list=', '.join(
                [
                    SQLProduct.objects.get(product_id=product_id).code
                    for product_id in set(excluded_products)
                ]
            ))
            self.respond(message)
        return filtered_transactions

    def send_errors(self, transactions, bad_codes):
        report_helper = ProductsReportHelper(self.user.sql_location, transactions)

        kwargs = {}

        if report_helper.reported_products():
            kwargs['stocks'] = ", ". join(
                [product.code for product in report_helper.reported_products().order_by('code')]
            )
            error_message = 'You reported: {stocks}, but there were errors: {err}'
        else:
            error_message = '{err}'

        missing = report_helper.missing_products()
        if missing:
            kwargs['missing'] = ", ".join([product.code for product in missing])
            error_message += " Please report {missing}"

        bad_codes = ', '.join(bad_codes)
        if bad_codes:
            kwargs['err'] = 'Unrecognized commodity codes: {bad_codes}.'.format(bad_codes=bad_codes)

        self.respond('{} {}'.format(error_message.format(**kwargs), six.text_type(ASSISTANCE_MESSAGE)))

    def send_ms_alert(self, previous_stockouts, transactions, ms_type):
        stockouts = {
            SQLProduct.objects.get(product_id=transaction.product_id).name
            for transaction in transactions
            if transaction.quantity == 0 and transaction.action == 'stockonhand'
        }

        with_stock = {
            SQLProduct.objects.get(product_id=transaction.product_id).name
            for transaction in transactions
            if transaction.quantity != 0 and transaction.action == 'stockonhand'
        }

        resolved_stockouts = previous_stockouts.intersection(with_stock)

        locations = self.sql_location.parent.get_descendants(include_self=True)\
            .filter(location_type__administrative=True)
        for sql_location in locations:
            for user in get_all_users_by_location(self.domain, sql_location.location_id):
                phone_number = get_preferred_phone_number_for_recipient(user)
                if not phone_number:
                    continue

                stockouts_and_resolved = [
                    (MS_RESOLVED_STOCKOUTS, resolved_stockouts),
                    (MS_STOCKOUT, stockouts)
                ]

                for message, data in stockouts_and_resolved:
                    if data:
                        message = message % {'products_names': ', '.join(data), 'ms_type': ms_type}
                        send_sms(self.domain, user, phone_number, message)

    def send_message_to_admins(self, message):
        in_charge_users = list(map(CommCareUser.wrap, iter_docs(
            CommCareUser.get_db(),
            [in_charge.user_id for in_charge in self.sql_location.facilityincharge_set.all()]
        )))
        for in_charge_user in in_charge_users:
            phone_number = get_preferred_phone_number_for_recipient(in_charge_user)
            if not phone_number:
                continue
            send_sms(self.sql_location.domain, in_charge_user, phone_number,
                     message % {'name': in_charge_user.full_name, 'location': self.sql_location.name})

    @property
    def parser(self):
        parser = EWSStockAndReceiptParser(self.domain_object, self.verified_contact)
        return parser

    def send_messages(self, parser, stockouts, transactions):
        if not parser.bad_codes:
            if self.sql_location.location_type.name == 'Regional Medical Store':
                self.send_ms_alert(stockouts, transactions, 'RMS')
            elif self.sql_location.location_type.name == 'Central Medical Store':
                self.send_ms_alert(stockouts, transactions, 'CMS')
            message, super_message = SOHAlerts(self.user, self.sql_location).get_alerts(transactions)
            if super_message:
                self.send_message_to_admins(super_message)
            self.respond(message)
        else:
            self.send_errors(transactions, parser.bad_codes)

    def handle(self):
        domain = Domain.get_by_name(self.domain)
        split_text = self.msg.text.split(' ', 1)
        if split_text[0].lower() == 'soh':
            text = split_text[1]
        elif split_text[0].startswith('soh'):
            text = split_text[0][3:]
        else:
            text = self.msg.text

        if not domain.commtrack_enabled:
            return False

        if not self.sql_location:
            self.respond(NO_SUPPLY_POINT_MESSAGE)
            return True

        try:
            parser = self.parser
            formatted_text = EWSFormatter().format(text)
            data = parser.parse(formatted_text)
            if not data:
                return False
            if EWS_INVALID_REPORT_RESPONSE.enabled(self.domain):
                filtered_transactions = self.get_valid_reports(data)

                if not filtered_transactions:
                    return True

                data['transactions'] = filtered_transactions

        except NotAUserClassError:
            return False
        except (SMSError, NoDefaultLocationException):
            self.respond(six.text_type(INVALID_MESSAGE))
            return True
        except ProductCodeException as e:
            self.respond(six.text_type(e))
            return True
        except Exception as e:
            if settings.UNIT_TESTING or settings.DEBUG:
                raise
            self.respond('problem with stock report: %s' % str(e))
            return True

        stockouts = set()
        if self.sql_location.location_type.name in ['Regional Medical Store', 'Central Medical Store']:
            stockouts = set(StockState.objects.filter(
                case_id=self.sql_location.supply_point_id,
                stock_on_hand=0
            ).values_list('sql_product__name', flat=True))

        process(domain.name, data)
        transactions = data['transactions']

        if not self.async_response:
            self.send_messages(parser, stockouts, transactions)
        else:
            send_soh_messages_task.delay(self, parser, stockouts, transactions)
        return True

    def help(self):
        self.respond(SOH_HELP_MESSAGE)
        return True
