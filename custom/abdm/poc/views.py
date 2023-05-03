from datetime import datetime, timedelta
import json

from rest_framework.decorators import (
    api_view,
)
from rest_framework.response import Response

from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.poc.gateway_calls import (
    gw_patient_profile_on_share,
    gw_care_context_on_discover,
    gw_care_context_on_init,
    gw_care_context_on_confirm,
    gw_consents_on_notify,
    gw_health_info_on_request,
    gw_health_info_on_transfer,
)

# Validations: Applicable for all API Views
# TODO Add validation for access token (Auth) and HIP ID that will be sent by gateway.
# TODO Add required params for request body. (See API spec)
# TODO Add API level additional validation as applicable. (See API spec)


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
@required_request_params(["requestId", "timestamp", "transactionId"])
def care_context_discover(request):
    request_data = request.data
    print("Patient care context request received!", request.data)
    _discover_patient_care_context(request_data)
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


def _discover_patient_care_context(request_data):
    # TODO: Logic for Discovery of Patient Care Context as HIP
    print("TODO: Logic for Discovery of Patient Care Context as HIP")
    gw_care_context_on_discover(request_data["requestId"], request_data['transactionId'])
    return True


# e8eb05d3-00f7-42af-bc7f-02311c36ebed
@api_view(["POST"])
@required_request_params(["requestId", "timestamp", "transactionId"])
def care_context_link_init(request):
    request_data = request.data
    print("Patient care context link request received!", request.data)
    _link_patient_care_context(request_data)
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


# TODO Validations as per the API specification
def _link_patient_care_context(request_data):
    # TODO: Logic for Discovery of Patient Care Context as HIP
    # TODO: Send OTP to Patient through HQ. (Mobile or email)
    print("TODO: Logic for Care context link to Patient..")
    print("TODO: Send OTP to Patient..")
    gw_care_context_on_init(request_data["requestId"], request_data['transactionId'])
    return True


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def care_context_link_confirm(request):
    request_data = request.data
    print("Patient care context link confirmation received!", request.data)
    _link_confirm_patient_care_context(request_data)
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


def _link_confirm_patient_care_context(request_data):
    # TODO Validate for linkRefNumber and token(OTP)
    print("TODO: Validation of Link Ref no and token..")
    gw_care_context_on_confirm(request_data["requestId"])
    return True


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def consent_notification(request):
    request_data = request.data
    print("consent notification received!", request.data)
    _save_user_consent(request_data)
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


def _save_user_consent(request_data):
    # TODO: DB: Store/Delete user consent into/from the database
    print("TODO: DB: Store user consent into the database..")
    gw_consents_on_notify(request_data["requestId"], request_data['notification']['consentId'])


@api_view(["POST"])
@required_request_params(["requestId", "timestamp", "transactionId"])
def health_info_request(request):
    request_data = request.data
    print("health_info_request received!", request.data)
    import threading
    x = threading.Thread(target=_process_health_info_request, args=(request_data,), daemon=True)
    x.start()
    print("Sending initial acknowledgement!")
    return Response(data={}, status=202)


def _process_health_info_request(request_data):
    # TODO: Validate consent status, period, encryption params etc
    gw_health_info_on_request(request_data["requestId"], request_data['transactionId'])
    _transfer_health_data(request_data)


def _transfer_health_data(request_data):
    # TODO: Fetch Health data stored from DB and generate FHIR bundle
    checksum, encryption_result, hip_key_material = _encrypt_data(request_data["hiRequest"]["keyMaterial"])
    data = {
        "pageNumber": 0,
        "pageCount": 0,
        "transactionId": request_data["transactionId"],
        "entries": [
            {
                "content": encryption_result['encryptedData'],
                "media": "application/fhir+json",
                "checksum": checksum,
                "careContextReference": "CC-201"
            },
            # {
            #     "link": "https://data-from.net/sa2321afaf12e13",
            #     "media": "application/fhir+json",
            #     "checksum": "string",
            #     "careContextReference": "NCC1701"
            # }
        ],
        "keyMaterial": hip_key_material
    }
    req_url = request_data["hiRequest"]["dataPushUrl"]
    headers = {"Content-Type": "application/json"}
    import requests
    print("transferring data to data push url")
    try:
        resp = requests.post(url=req_url, data=json.dumps(data), headers=headers)
        print("Health data transfer status code: resp.status code", resp.status_code)
        print("Health data transfer resp.text", resp.text)
    except Exception as e:
        print("exception", e)
    gw_health_info_on_transfer(request_data["hiRequest"]["consent"]["id"], request_data["transactionId"])


def _encrypt_data(hiu_key_material):
    from custom.abdm.poc.encryption_util import getEcdhKeyMaterial, encryptData
    sender_key_material = getEcdhKeyMaterial()
    with open('custom/abdm/poc/data/pathology_sample.json') as user_file:
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
            "expiry": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "parameters": "Curve25519/32byte random key",
            "keyValue": sender_key_material["publicKey"]
        },
        "nonce": sender_key_material["nonce"]
    }
    print(f"checksum: {checksum}")
    print(f"encryption_result: {encryption_result}")
    print(f"hip_key_material: {hip_key_material}")
    return checksum, encryption_result, hip_key_material
