from rest_framework.decorators import (
    api_view,
)
from rest_framework.response import Response

from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.poc.gateway_calls import (
    gw_patient_profile_on_share,
    gw_care_context_on_discover,
    gw_consents_on_notify
)

# Applicable for all API Views
# TODO Add more params for request validation.
# TODO Add validation for access token that will be sent by gateway.


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def patient_profile_share(request):
    request_data = request.data
    print("Patient Profile Details received!", request.data)
    print("request.meta", request.META)
    # TODO Execute below function async
    _process_patient_profile(request_data)
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


def _process_patient_profile(request_data):
    # TODO Logic for Action on these details as an HIP
    print("TODO: Saving these details of patient as an HIP")
    gw_patient_profile_on_share(request_data["requestId"], request_data['profile']['patient']['healthId'])
    return True


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def patient_care_context(request):
    request_data = request.data
    print("Patient care context request received!", request.data)
    print("request.meta", request.META)
    _discover_patient_care_context(request_data)
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


def _discover_patient_care_context(request_data):
    # TODO: Logic for Discovery of Patient Care Context as HIP
    print("TODO: Logic for Discovery of Patient Care Context as HIP")
    gw_care_context_on_discover(request_data["requestId"], request_data['transactionId'])
    return True


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def consent_notification(request):
    request_data = request.data
    print("consent notification received!", request.data)
    print("request.meta", request.META)
    gw_consents_on_notify(request_data["requestId"], request_data['notification']['consentId'])
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)
