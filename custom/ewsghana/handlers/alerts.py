from corehq.apps.sms.mixin import PhoneNumberInUseException, VerifiedNumber
from custom.ewsghana.reminders import REGISTER_HELP, REGISTRATION_CONFIRM
from django.contrib.auth.models import User
from corehq.apps.users.models import CommCareUser
from custom.logistics.commtrack import add_location
from custom.ilsgateway.models import ILSGatewayConfig
from custom.ilsgateway.tanzania.handlers import get_location
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from custom.ilsgateway.tanzania.reminders import Languages
from corehq.apps.products.models import SQLProduct
from custom.ewsghana.alerts import DOMAIN, COMPLETE_REPORT, INCOMPLETE_REPORT, WITHOUT_RECEIPTS, ABOVE_THRESHOLD, \
    BELOW_REORDER_LEVELS
from custom.ewsghana.alerts.alerts import report_completion_check
from corehq.apps.sms.api import send_sms_to_verified_number
from corehq.apps.commtrack.sms import *
import re
from corehq.apps.commtrack import const
from corehq.apps.commtrack.models import SupplyPointCase, StockState


class AlertsHandler(KeywordHandler):

    def handle(self):

        text = self.args
        verified_contact = self.verified_contact

        domain = Domain.get_by_name(verified_contact.domain)
        if not domain.commtrack_enabled:
            return False

        try:
            data = StockAndReceiptParser(domain, verified_contact).parse(text.lower())
            if not data:
                return False
        except NotAUserClassError:
            return False
        except Exception, e:  # todo: should we only trap SMSErrors?
            if settings.UNIT_TESTING or settings.DEBUG:
                raise
            send_sms_to_verified_number(verified_contact, 'problem with stock report: %s' % str(e))
            return True

        process(domain.name, data)
        report_completion_check(self.user)  # sends COMPLETE_REPORT or INCOMPLETE_REPORT
        # send_confirmation(verified_contact, data)
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
        products_without_receipts = set()
        products_above = set()
        products_below = set()
        above = 100  # todo random value, find thresholds values
        below = 10  # random value
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
                    # addition to StockAndReceiptParser copied from corehq starts here
                    last_stock = StockState.objects.get(case_id=self.case_id,
                                                        product_id=p.product_id).stock_on_hand
                    stock = value.split('.')[0]
                    receipt = value.split('.')[1]
                    if stock > last_stock and receipt == 0:
                        products_without_receipts.add(p)
                    elif stock > above:
                        products_above.add(p)
                    elif stock < below:
                        products_below.add(p)
                    # ends here
                    else:
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
        # addition to StockAndReceiptParser copied from corehq starts here
        elif products_without_receipts:
            raise SMSError(WITHOUT_RECEIPTS % ', '.join(sorted(str(product)
                                                               for product in products_without_receipts)))
        elif products_below:
            message = BELOW_REORDER_LEVELS % (self.v.owner, self.v.owner.location,
                                              ", ".join(sorted([str(product) for product in products_below])))
            raise SMSError(message)
        elif products_above:
            raise SMSError(ABOVE_THRESHOLD % (self.v.owner, self.v.owner.location,
                                              ", ".join(sorted([str(product) for product in products_above]))))
        # ends here
