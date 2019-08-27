from custom.ilsgateway.tanzania.handlers.zipline import ZiplineGenericHandler
from custom.ilsgateway.tanzania.reminders import EMG_ERROR, EMG_HELP
from custom.zipline.api import initiate_emergency_order


class ParseError(Exception):
    pass


class EmergencyHandler(ZiplineGenericHandler):

    error_message = EMG_ERROR
    help_message = EMG_HELP

    def invoke_api_function(self, quantities_list):
        initiate_emergency_order(
            self.domain,
            self.user,
            self.verified_contact.phone_number,
            self.sql_location,
            quantities_list
        )

    def send_success_message(self):
        pass
