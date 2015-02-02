from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ewsghana.alerts.alerts import report_completion_check, stock_alerts
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.commtrack.sms import *
import re
from corehq.apps.commtrack import const


class AlertsHandler(KeywordHandler):

    def handle(self):
        verified_contact = self.verified_contact
        user = verified_contact.owner
        domain = Domain.get_by_name(verified_contact.domain)
        text = self.msg.text

        if not domain.commtrack_enabled:
            return False
        try:
            data = StockAndReceiptParser(domain, verified_contact).parse(text)
            if not data:
                return False
        except NotAUserClassError:
            return False
        except Exception, e:  # todo: should we only trap SMSErrors?
            if settings.UNIT_TESTING or settings.DEBUG:
                raise
            send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
            return True
        transactions = data['transactions']

        if not stock_alerts(transactions, user) and user.location:
            process(domain.name, data)
            report_completion_check(self.user)
        return True


class StockAndReceiptParser(StockReportParser):
    """
    This parser (originally written for EWS) allows
    a slightly different requirement for SMS formats,
    this class exists to break that functionality
    out of the default SMS handler to live in the ewsghana

    They send messages of the format:

        'soh nets 100.22'

    In this example, the data reflects:

        nets = product sms code
        100 = the facility stating that they have 100 nets
        20 = the facility stating that they received 20 in this period

    There is some duplication here, but it felt better to
    add duplication instead of complexity. The goal is to
    override only the couple methods that required modifications.
    """
    def looks_like_prod_code(self, code):
        """
        Special for EWS, this version doesn't consider "10.20"
        as an invalid quantity.
        """
        try:
            float(code)
            return False
        except ValueError:
            return True

    def single_action_transactions(self, action, args, make_tx):
        products = []
        for arg in args:
            if self.looks_like_prod_code(arg):
                products.append(self.product_from_code(arg))
            else:
                if not products:
                    raise SMSError('quantity "%s" doesn\'t have a product' % arg)
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
                    yield make_tx(
                        product=p,
                        action=const.StockActions.RECEIPTS,
                        quantity=value.split('.')[1]
                    )
                    yield make_tx(
                        product=p,
                        action=const.StockActions.STOCKONHAND,
                        quantity=value.split('.')[0]
                    )
                products = []
        if products:
            raise SMSError('missing quantity for product "%s"' % products[-1].code)
