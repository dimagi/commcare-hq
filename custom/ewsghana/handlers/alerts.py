from corehq.apps.commtrack.models import StockState
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from custom.ewsghana.handlers import INVALID_MESSAGE, INVALID_PRODUCT_CODE, ASSISTANCE_MESSAGE,\
    MS_STOCKOUT, MS_RESOLVED_STOCKOUTS
from collections import defaultdict
from casexml.apps.stock.const import SECTION_TYPE_STOCK
from casexml.apps.stock.models import StockTransaction
from corehq.apps.locations.models import SQLLocation
from corehq.apps.products.models import SQLProduct
from corehq.toggles import EWS_INVALID_REPORT_RESPONSE
from custom.ewsghana.reminders import ERROR_MESSAGE
from custom.ewsghana.utils import ProductsReportHelper
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ewsghana.alerts.alerts import stock_alerts
from corehq.apps.commtrack.sms import *
from custom.ilsgateway.tanzania.reminders import SOH_HELP_MESSAGE


class ProductCodeException(Exception):
    pass


class EWSFormatter(object):

    REC_SEPARATOR = '-'

    def _clean_string(self, string):
        if not string:
            return string
        mylist = list(string)
        newstring = string[0]
        i = 1
        while i < len(mylist) - 1:
            if mylist[i] == ' ' and mylist[i - 1].isdigit() and mylist[i + 1].isdigit():
                newstring += self.REC_SEPARATOR
            else:
                newstring = newstring + mylist[i]
            i += 1
        newstring = newstring + string[-1]
        string = newstring

        string = string.replace(' ', '')
        separators = [',', '/', ';', '*', '+', '-']
        for mark in separators:
            string = string.replace(mark, self.REC_SEPARATOR)
        junk = ['\'', '\"', '`', '(', ')']
        for mark in junk:
            string = string.replace(mark, '')
        return string.lower()

    def _getTokens(self, string):
        mylist = list(string)
        token = ''
        i = 0
        while i < len(mylist):
            token = token + mylist[i]
            if i + 1 == len(mylist):
                # you've reached the end
                yield token
            elif (mylist[i].isdigit() and not mylist[i + 1].isdigit()
                  or mylist[i].isalpha() and not mylist[i + 1].isalpha()
                  or not mylist[i].isalnum() and mylist[i + 1].isalnum()):
                yield token
                token = ''
            i += 1

    def format(self, string):
        """
        Old parse method, used in Ghana for more 'interesting' parsing.
        Moved from: https://github.com/dimagi/rapidsms-logistics/blob/7a1433abbda4ec27dc8f4c5da14c0f5689abd202/logistics/models.py#L1430
        """
        if not string:
            return
        match = re.search("[0-9]", string)
        if not match:
            return string
        string = self._clean_string(string)
        an_iter = self._getTokens(string)
        commodity = None
        valid = False

        result = ''

        while True:
            try:
                while commodity is None or not commodity.isalpha():
                    commodity = an_iter.next().lower()
                count = an_iter.next()
                while not count.isdigit():
                    count = an_iter.next()
                result += '{} {}'.format(commodity, count)
                valid = True
                token_a = an_iter.next()
                if not token_a.isalnum():
                    token_b = an_iter.next()
                    while not token_b.isalnum():
                        token_b = an_iter.next()
                    if token_b.isdigit():
                        # if digit, then the user is reporting receipts
                        result += '.{} '.format(token_b)
                        commodity = None
                        valid = True
                    else:
                        # if alpha, user is reporting soh, so loop
                        commodity = token_b
                        valid = True
                else:
                    commodity = token_a
                    valid = True
            except ValueError:
                commodity = None
                continue
            except StopIteration:
                break
        if not valid:
            return string
        return result.strip()


class EWSStockAndReceiptParser(StockAndReceiptParser):

    def __init__(self, domain, v):
        super(EWSStockAndReceiptParser, self).__init__(domain, v)
        self.bad_codes = set()

    def product_from_code(self, prod_code):
        try:
            return super(EWSStockAndReceiptParser, self).product_from_code(prod_code)
        except SMSError:
            return None

    def single_action_transactions(self, action, args):
        products = []
        for idx, arg in enumerate(args):
            if self.looks_like_prod_code(arg):
                product = self.product_from_code(arg)
                if product:
                    products.append(product)
                else:
                    if idx == 0:
                        raise ProductCodeException(INVALID_PRODUCT_CODE % arg)
                    self.bad_codes.add(arg)
            else:
                if not products:
                    continue
                if len(products) > 1:
                    raise SMSError('missing quantity for product "%s"' % products[-1].code)

                # NOTE also custom code here, must be formatted like 11.22
                if re.compile("^\d+\.\d+$").match(arg):
                    value = arg
                else:
                    raise SMSError('could not understand product quantity "%s"' % arg)

                for p in products:
                    # for EWS we have to do two transactions, one being a receipt
                    # and second being a transaction (that's reverse of the order
                    # the user provides them)
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location['location'].get_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=const.StockActions.RECEIPTS,
                        quantity=Decimal(value.split('.')[1])
                    )
                    yield StockTransactionHelper(
                        domain=self.domain.name,
                        location_id=self.location['location'].get_id,
                        case_id=self.case_id,
                        product_id=p.get_id,
                        action=const.StockActions.STOCKONHAND,
                        quantity=Decimal(value.split('.')[0])
                    )
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)


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

        self.respond('{} {}'.format(error_message.format(**kwargs), unicode(ASSISTANCE_MESSAGE)))

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

        if ms_type == 'RMS':
            locations = self.sql_location.parent.get_descendants().filter(location_type__administrative=False)
        elif ms_type == 'CMS':
            locations = self.sql_location.parent.get_descendants().filter(location_type__administrative=True)
        else:
            return

        for sql_location in locations:
            for user in get_users_by_location_id(self.domain, sql_location.location_id):
                verified_number = user.get_verified_number()
                if not verified_number:
                    continue

                if stockouts:
                    send_sms_to_verified_number(
                        verified_number,
                        MS_STOCKOUT % {'products_names': ', '.join(stockouts), 'ms_type': ms_type}
                    )

                if resolved_stockouts:
                    send_sms_to_verified_number(
                        verified_number,
                        MS_RESOLVED_STOCKOUTS % {
                            'products_names': '. '.join(resolved_stockouts), 'ms_type': ms_type
                        }
                    )

    def handle(self):
        verified_contact = self.verified_contact
        user = verified_contact.owner
        domain = Domain.get_by_name(verified_contact.domain)
        split_text = self.msg.text.split(' ', 1)
        if split_text[0].lower() == 'soh':
            text = split_text[1]
        elif split_text[0].startswith('soh'):
            text = split_text[0][3:]
        else:
            text = self.msg.text

        if not domain.commtrack_enabled:
            return False
        try:
            parser = EWSStockAndReceiptParser(domain, verified_contact)
            formatted_text = EWSFormatter().format(text)

            data = parser.parse(formatted_text)
            if not data:
                return False
            if EWS_INVALID_REPORT_RESPONSE.enabled(self.domain):
                filtered_transactions = self.get_valid_reports(data, verified_contact)

                if not filtered_transactions:
                    return True

                data['transactions'] = filtered_transactions

        except NotAUserClassError:
            return False
        except SMSError:
            send_sms_to_verified_number(verified_contact, unicode(INVALID_MESSAGE))
            return True
        except ProductCodeException as e:
            send_sms_to_verified_number(verified_contact, e.message)
            return True
        except Exception, e:  # todo: should we only trap SMSErrors?
            if settings.UNIT_TESTING or settings.DEBUG:
                raise
            send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
            return True

        stockouts = set()
        if self.sql_location.location_type.name in ['Regional Medical Store', 'Central Medical Store']:
            stockouts = set(StockState.objects.filter(
                case_id=self.sql_location.supply_point_id,
                stock_on_hand=0
            ).values_list('sql_product__name', flat=True))

        process(domain.name, data)
        transactions = data['transactions']
        if not parser.bad_codes:
            if self.sql_location.location_type.name == 'Regional Medical Store':
                self.send_ms_alert(stockouts, transactions, 'RMS')
            elif self.sql_location.location_type.name == 'Central Medical Store':
                self.send_ms_alert(stockouts, transactions, 'CMS')
            stock_alerts(transactions, user)
        else:
            self.send_errors(transactions, parser.bad_codes)

        return True

    def help(self):
        self.respond(SOH_HELP_MESSAGE)
        return True
