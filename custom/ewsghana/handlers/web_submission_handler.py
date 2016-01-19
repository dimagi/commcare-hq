from collections import namedtuple

from corehq.apps.reminders.util import get_preferred_phone_number_for_recipient
from custom.ewsghana.handlers.helpers.stock_and_receipt_parser import EWSStockAndReceiptParser
from custom.ewsghana.handlers.soh import SOHHandler
from custom.ewsghana.utils import send_sms

VerifiedNumberAdapter = namedtuple('VerifiedNumberAdapter', ['owner', 'phone_number', 'domain', 'owner_id'])


class WebSubmissionHandler(SOHHandler):

    async_response = True

    def __init__(self, user, domain, msg, sql_location):
        super(WebSubmissionHandler, self).__init__(user, domain, [], msg, None)
        self._sql_location = sql_location

    @property
    def sql_location(self):
        return self._sql_location

    @property
    def parser(self):
        return EWSStockAndReceiptParser(
            self.domain_object,
            VerifiedNumberAdapter(self.user, 'ewsghana-input-stock', self.domain, self.user.get_id),
            self.sql_location.couch_location
        )

    def respond(self, message, **kwargs):
        phone_number = get_preferred_phone_number_for_recipient(self.user)
        if not phone_number:
            return

        send_sms(self.domain, self.user, phone_number, unicode(message % kwargs))
