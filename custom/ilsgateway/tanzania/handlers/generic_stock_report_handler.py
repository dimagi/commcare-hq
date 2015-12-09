from django.conf import settings
from corehq.apps.commtrack.exceptions import NotAUserClassError
from corehq.apps.commtrack.sms import process
from corehq.apps.sms.api import send_sms_to_verified_number
from custom.ilsgateway.tanzania.handlers.ils_stock_report_parser import ILSStockReportParser
from custom.ilsgateway.tanzania.handlers.keyword import KeywordHandler


class GenericStockReportHandler(KeywordHandler):

    formatter = None
    status_type = None
    status_value = None

    @property
    def data(self):
        return ILSStockReportParser(
            self.domain_object,
            self.verified_contact,
            self.formatter()
        ).parse(self.msg.text)

    def get_message(self, data):
        raise NotImplemented()

    def on_success(self):
        raise NotImplemented()

    def handle(self):
        location = self.user.location
        domain = self.domain_object

        location_id = self.location_id

        if not location_id:
            return False

        if location.location_type == 'FACILITY':
            try:
                data = self.data
                if not data:
                    return True
                process(domain.name, data)
                self.on_success()
                self.respond(self.get_message(data))
            except NotAUserClassError:
                return True
            except Exception, e:  # todo: should we only trap SMSErrors?
                if settings.UNIT_TESTING or settings.DEBUG:
                    raise
                send_sms_to_verified_number(self.verified_contact, 'problem with stock report: %s' % str(e))
        return True
