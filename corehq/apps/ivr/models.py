from corehq.apps.sms.mixin import MobileBackend


class IVRBackend(MobileBackend):
    backend_type = 'IVR'

    def initiate_outbound_call(call, logged_subevent, ivr_data=None):
        raise NotImplementedError("Please implement this method")

    def get_response(gateway_session_id, ivr_responses, collect_input=False,
            hang_up=True, input_length=None)
        raise NotImplementedError("Please implement this method")
