from collections import defaultdict
from casexml.apps.stock.const import SECTION_TYPE_STOCK
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.toggles import EWS_INVALID_REPORT_RESPONSE
from custom.ewsghana.reminders import ERROR_MESSAGE
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ewsghana.alerts.alerts import stock_alerts
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.commtrack.sms import *


def get_transactions_by_product(transactions):
    result = defaultdict(list)
    for tx in transactions:
        result[tx.product_id].append(tx)
    return result


class AlertsHandler(KeywordHandler):

    def get_valid_reports(self, data, verified_contact):
        filtered_transactions = []
        excluded_products = []
        for product_id, transactions in get_transactions_by_product(data['transactions']).iteritems():
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
            send_sms_to_verified_number(verified_contact, message)
        return filtered_transactions

    def handle(self):
        verified_contact = self.verified_contact
        user = verified_contact.owner
        domain = Domain.get_by_name(verified_contact.domain)
        splitted_text = self.msg.text.split()
        if splitted_text[0].lower() == 'soh':
            text = ' '.join(self.msg.text.split()[1:])
        else:
            text = self.msg.text

        if not domain.commtrack_enabled:
            return False
        try:
            data = StockAndReceiptParser(domain, verified_contact).parse(text)
            if not data:
                return False
            if EWS_INVALID_REPORT_RESPONSE.enabled(self.domain):
                filtered_transactions = self.get_valid_reports(data, verified_contact)

                if not filtered_transactions:
                    return True

                data['transactions'] = filtered_transactions

        except NotAUserClassError:
            return False
        except Exception, e:  # todo: should we only trap SMSErrors?
            if settings.UNIT_TESTING or settings.DEBUG:
                raise
            send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
            return True

        process(domain.name, data)
        transactions = data['transactions']
        stock_alerts(transactions, user)
        return True
