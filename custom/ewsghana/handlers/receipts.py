from corehq.apps.domain.models import Domain
from corehq.apps.commtrack.exceptions import NotAUserClassError
from corehq.apps.products.models import SQLProduct
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ewsghana.reminders import RECEIPT_CONFIRM
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler
from corehq.apps.commtrack.sms import StockReportParser, process
import settings


class ReceiptsHandler(KeywordHandler):

    def help(self):
        pass

    def handle(self):
        verified_contact = self.verified_contact
        domain = Domain.get_by_name(verified_contact.domain)
        text = self.msg.text

        try:
            data = StockReportParser(domain, verified_contact).parse(text)
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
        products = [SQLProduct.objects.get(product_id=transaction.product_id).code for transaction in transactions]
        process(domain.name, data)
        send_sms_to_verified_number(verified_contact, RECEIPT_CONFIRM % {'products': ' '.join(products)})
        return True
