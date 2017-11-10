from __future__ import absolute_import
from custom.ilsgateway.tanzania.handlers.zipline import ZiplineGenericHandler
from custom.ilsgateway.tanzania.reminders import REC_CONFIRMATION, REC_ERROR, REC_HELP
from custom.zipline.api import process_receipt_confirmation


class ReceiptHandler(ZiplineGenericHandler):

    error_message = REC_ERROR
    help_message = REC_HELP

    def invoke_api_function(self, quantities_list):
        process_receipt_confirmation(self.domain, self.user, self.sql_location, quantities_list)

    def send_success_message(self):
        self.respond(REC_CONFIRMATION)
