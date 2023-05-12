from datetime import datetime, timedelta
import json

from django.shortcuts import render
from rest_framework.decorators import (
    api_view,
)
from rest_framework.response import Response

from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.poc.const import SAMPLE_FHIR_BUNDLE
from custom.abdm.poc.hip.gateway_calls import (
    gw_patient_profile_on_share,
    gw_care_context_on_discover,
    gw_care_context_link_on_init,
    gw_care_context_link_on_confirm,
    gw_consents_on_notify,
    gw_health_info_on_request,
    gw_health_info_on_transfer,
)
from custom.abdm.models import Patient

# Validations: Applicable for all API Views
# TODO Add validation for access token (Auth) and HIP ID that will be sent by gateway.
# TODO Add required params for request body. (See API spec)
# TODO Add API level additional validation as applicable. (See API spec)
# TODO Execute gateway callback functions asynchronously


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def patient_profile_share(request):
    request_data = request.data
    print("HIP: Request Received from GW: patient_profile_share", request.data)
    print("request.meta", request.META)
    _process_patient_profile(request_data)
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


def _process_patient_profile(request_data):
    # TODO Logic for Action on these details as an HIP
    patient_details = request_data['profile']['patient']
    try:
        patient = Patient.objects.get(abha_address=patient_details['healthId'])
    except Patient.DoesNotExist:
        patient = Patient(name=patient_details['name'], abha_address=patient_details['healthId'],
                          health_id_number=patient_details['healthIdNumber'], address=patient_details['address'],
                          identifiers=patient_details['identifiers'])
        patient.save()
    gw_patient_profile_on_share(request_data["requestId"], request_data['profile']['patient']['healthId'])


@api_view(["POST"])
@required_request_params(["requestId", "timestamp", "transactionId"])
def care_context_discover(request):
    request_data = request.data
    print("HIP: Request Received from GW: care_context_discover", request.data)
    _discover_patient_care_context(request_data)
    return Response(data={}, status=202)


def _discover_patient_care_context(request_data):
    # TODO: Logic for Discovery of Patient Care Context as HIP
    gw_care_context_on_discover(request_data["requestId"], request_data['transactionId'])


@api_view(["POST"])
@required_request_params(["requestId", "timestamp", "transactionId"])
def care_context_link_init(request):
    request_data = request.data
    print("HIP: Request Received from GW: Patient care context link!", request.data)
    _link_patient_care_context(request_data)
    return Response(data={}, status=202)


def _link_patient_care_context(request_data):
    # TODO: Logic for Discovery of Patient Care Context as HIP
    # TODO: Send OTP to Patient through HQ. (Mobile or email)
    gw_care_context_link_on_init(request_data["requestId"], request_data['transactionId'])


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def care_context_link_confirm(request):
    request_data = request.data
    print("HIP: Request Received from GW: Patient care context link confirmation!", request.data)
    _link_confirm_patient_care_context(request_data)
    return Response(data={}, status=202)


def _link_confirm_patient_care_context(request_data):
    # TODO Validate for linkRefNumber and token(OTP)
    gw_care_context_link_on_confirm(request_data["requestId"])


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def consent_notification(request):
    request_data = request.data
    print("HIP: Request Received from GW: consent notification received!", request.data)
    _save_user_consent(request_data)
    return Response(data={}, status=202)


def _save_user_consent(request_data):
    # TODO: DB: Store/Update user consent at the database
    gw_consents_on_notify(request_data["requestId"], request_data['notification']['consentId'])


@api_view(["POST"])
@required_request_params(["requestId", "timestamp", "transactionId"])
def health_info_request(request):
    request_data = request.data
    print("HIP: Request Received from GW: health_info_request received!", request.data)
    # TODO Use async mechanism below
    import threading
    x = threading.Thread(target=_process_health_info_request, args=(request_data,), daemon=True)
    x.start()
    return Response(data={}, status=202)


def _process_health_info_request(request_data):
    # TODO: Validate consent status, period, encryption params etc
    gw_health_info_on_request(request_data["requestId"], request_data['transactionId'])
    _transfer_health_data(request_data)


def _transfer_health_data(request_data):
    # TODO: Fetch Health data stored from DB and generate FHIR bundle
    checksum, encryption_result, hip_key_material = _encrypt_data(request_data["hiRequest"]["keyMaterial"])
    data = {
        "pageNumber": 1,
        "pageCount": 1,
        "transactionId": request_data["transactionId"],
        "entries": [
            {
                "content": encryption_result['encryptedData'],
                "media": "application/fhir+json",
                "checksum": checksum,
                "careContextReference": "CC-201"
            }
        ],
        "keyMaterial": hip_key_material
    }
    req_url = request_data["hiRequest"]["dataPushUrl"]
    headers = {"Content-Type": "application/json"}
    import requests
    print(f"HIP: Transferring data to data push url: {req_url} provided by HIU")
    try:
        resp = requests.post(url=req_url, data=json.dumps(data), headers=headers)
        print("HIP: Health data transfer status code from HIU: ", resp.status_code)
        print("HIP: Health data transfer response from HIU: ", resp.text)
    except Exception as e:
        print("exception", e)
    gw_health_info_on_transfer(request_data["hiRequest"]["consent"]["id"], request_data["transactionId"])


def _encrypt_data(hiu_key_material):
    from custom.abdm.poc.encryption_util import getEcdhKeyMaterial, encryptData
    sender_key_material = getEcdhKeyMaterial()
    with open(SAMPLE_FHIR_BUNDLE) as user_file:
        parsed_json = json.load(user_file)
    fhir_sample_json = json.dumps(parsed_json)
    import hashlib
    checksum = hashlib.md5(fhir_sample_json.encode('utf-8')).hexdigest()
    encryption_result = encryptData({
        'stringToEncrypt': fhir_sample_json,
        'senderNonce': sender_key_material['nonce'],
        'requesterNonce': hiu_key_material['nonce'],
        'senderPrivateKey': sender_key_material['privateKey'],
        'requesterPublicKey': hiu_key_material['dhPublicKey']['keyValue']
    })
    hip_key_material = {
        "cryptoAlg": "ECDH",
        "curve": "Curve25519",
        "dhPublicKey": {
            "expiry": (datetime.utcnow() + timedelta(days=10)).isoformat(),
            "parameters": "Curve25519",
            "keyValue": sender_key_material["x509PublicKey"]
        },
        "nonce": sender_key_material["nonce"]
    }
    return checksum, encryption_result, hip_key_material


@api_view(["GET"])
def fetch_patients(request):
    print("HIU: fetch consents", request.data)
    patients = Patient.objects.all().order_by('-created_date').values()
    return render(request, "abdm/hip_patients.html", {'patients': patients})
