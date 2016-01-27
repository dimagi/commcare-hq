from corehq.apps.sms.mixin import UnrecognizedBackendException
from corehq.apps.sms.models import SQLMobileBackend
from corehq.apps.sms.util import get_available_backends


class UnrecognizedIVRBackendException(UnrecognizedBackendException):
    pass


class SQLIVRBackend(SQLMobileBackend):
    class Meta:
        app_label = 'sms'
        proxy = True

    def initiate_outbound_call(self, call, logged_subevent, ivr_data=None):
        """
        Should return False if an error occurred and the call should be retried.
        Should return True if the call should not be retried (either because it
        was queued successfully or because an unrecoverable error occurred).
        """
        raise NotImplementedError("Please implement this method")

    def get_response(self, gateway_session_id, ivr_responses, collect_input=False,
            hang_up=True, input_length=None):
        raise NotImplementedError("Please implement this method")

    def cache_first_ivr_response(self):
        """
        If you want the framework to cache the first response that HQ will have
        to the gateway, set this to True.
        """
        return False

    def set_first_ivr_response(self, call, gateway_session_id, ivr_data):
        call.xforms_session_id = ivr_data.session.session_id
        call.use_precached_first_response = True
        call.first_response = self.get_response(
            gateway_session_id,
            ivr_data.ivr_responses,
            collect_input=True,
            hang_up=False,
            input_length=ivr_data.input_length
        )
