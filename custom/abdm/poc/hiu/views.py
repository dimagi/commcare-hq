import uuid
from datetime import datetime, timedelta
import json

from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.shortcuts import render
from rest_framework.decorators import (
    api_view,
)
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED

from custom.abdm.milestone_one.utils.decorators import required_request_params
from custom.abdm.poc.hiu.gateway_calls import (
    gw_consent_request_init,
    gw_consents_on_notify,
    gw_fetch_consents,
    gw_health_info_request,
    gw_health_info_notify,
)
from custom.abdm.models import ConsentRequest, CONSENT_REQUEST_STATUS_GRANTED
from custom.abdm.poc.const import HIU_KEY_MATERIAL_JSON_PATH

from custom.abdm.poc.hiu.serializers import ConsentInitSerializer

# Validations: Applicable for all API Views
# TODO Add validation for access token (Auth) and HIU ID that will be sent by gateway. (See API spec)
# TODO Add required params for request body. (See API spec)
# TODO Add API level additional validation as applicable. (See API spec)

# TODO: Processing as needed for each API(flow) asynchronously
# TODO Execute gateway callback and processing functions asynchronously

# TEST DATA: Saving last key material
with open(HIU_KEY_MATERIAL_JSON_PATH) as user_file:
    key_material = json.load(user_file)

CONSENT_ID = None


@api_view(["POST"])
def generate_consent_request(request):
    print("HIU: Generate consent Request", request.data)
    serializer = ConsentInitSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    # TODO Datetime convert to utc or accept utctime
    # request_data = request.data
    # patient_abha_address = request_data['patientIdentifier']
    # consent_purpose = request_data['purposeOfRequest']
    # health_info_from = datetime.strptime(request_data['healthInfoFrom'], '%Y-%m-%d').isoformat()
    # health_info_to = datetime.strptime(request_data['healthInfoTo'], '%Y-%m-%d').isoformat()
    # health_info_type = request_data['healthInfoType']
    # consent_expiry = datetime.strptime(request_data['consentExpiry'], '%Y-%m-%dT%H:%M').isoformat()
    # consent_request = ConsentRequest(request_id=str(uuid.uuid4()), patient_abha_address=patient_abha_address)
    # consent_request.save()
    # gw_consent_request_init(consent_request.request_id, patient_abha_address, consent_purpose,
    #                         health_info_from, health_info_to, health_info_type, consent_expiry)
    return HttpResponse(status=HTTP_202_ACCEPTED)


# ONLY FOR DEMO
@api_view(["POST", "GET"])
def generate_consent_request_ui(request):
    print("HIU: Generate consent Request", request.data)
    if request.method == "GET":
        return render(request, "abdm/request_consent.html", {})
    else:
        # TODO Datetime convert to utc or accept utctime
        request_data = request.data
        patient_abha_address = request_data['patientIdentifier']
        consent_purpose = request_data['purposeOfRequest']
        health_info_from = datetime.strptime(request_data['healthInfoFrom'], '%Y-%m-%d').isoformat()
        health_info_to = datetime.strptime(request_data['healthInfoTo'], '%Y-%m-%d').isoformat()
        health_info_type = request_data['healthInfoType']
        consent_expiry = datetime.strptime(request_data['consentExpiry'], '%Y-%m-%dT%H:%M').isoformat()
        consent_request = ConsentRequest(request_id=str(uuid.uuid4()), patient_abha_address=patient_abha_address)
        consent_request.save()
        gw_consent_request_init(consent_request.request_id, patient_abha_address, consent_purpose,
                                health_info_from, health_info_to, health_info_type, consent_expiry)
        return HttpResponseRedirect(reverse('fetch_consents'))


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def consent_requests_on_init(request):
    request_data = request.data
    print("HIU: Request Received from GW: consent_requests_on_init", request.data)
    print("request.meta", request.META)
    consent_request = ConsentRequest.objects.get(request_id=request_data['resp']['requestId'])
    if request_data.get('consentRequest'):
        consent_request.consent_request_id = request_data['consentRequest']['id']
    if request_data.get('error'):
        consent_request.status = 'ERROR'
    consent_request.save()
    return Response(data={}, status=202)


# TODO
@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def consent_requests_on_status(request):
    request_data = request.data
    print("HIU: Request Received from GW: consent_requests_on_status", request_data)
    return Response(data={}, status=202)


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def consents_hiu_notify(request):
    request_data = request.data
    print("HIU: Request Received from GW: consents_hiu_notify", request.data)
    _store_consent_details(request_data)
    return Response(data={}, status=202)


def _store_consent_details(request_data):
    # TODO Add support for multiple artefacts
    consent_request_id = request_data['notification']['consentRequestId']
    consent_request = ConsentRequest.objects.get(consent_request_id=consent_request_id)
    consent_request.status = request_data['notification']['status']
    if consent_request.status == CONSENT_REQUEST_STATUS_GRANTED:
        consent_request.artefact_id = request_data['notification']['consentArtefacts'][0]['id']
        gw_fetch_consents(consent_request.artefact_id)
    consent_request.save()
    gw_consents_on_notify(request_data["requestId"], request_data['notification']['consentArtefacts'])


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def consents_on_fetch(request):
    request_data = request.data
    print("HIU: fetch consent details", request.data)
    _save_consent_details(request_data)
    return Response(data={}, status=202)


def _save_consent_details(request_data):
    # TODO: DB: Update consent artefact details
    consent_request = ConsentRequest.objects.get(artefact_id=request_data["consent"]["consentDetail"]["consentId"])
    consent_request.details = request_data["consent"]["consentDetail"]
    consent_request.save()


@api_view(["GET"])
def fetch_consents(request):
    print("HIU: fetch consents", request.data)
    consents = ConsentRequest.objects.all().order_by('-created_date').values()
    return render(request, "abdm/consents.html", {'consents': consents})


@api_view(["POST"])
@required_request_params(["consent_artefact_id"])
def request_health_info(request):
    print("HIU: Request Health Info", request.data)
    consent_artefact_id = request.data['consent_artefact_id']
    consent_request = ConsentRequest.objects.get(artefact_id=consent_artefact_id)
    hiu_key_material = {
        "cryptoAlg": "ECDH",
        "curve": "Curve25519",
        "dhPublicKey": {
            "expiry": (datetime.utcnow() + timedelta(days=1)).isoformat(),
            "parameters": "Curve25519/32byte random key",
            "keyValue": key_material["publicKey"]
        },
        "nonce": key_material["nonce"]
    }
    gw_health_info_request(consent_artefact_id, hiu_key_material, consent_request)
    return Response(data={}, status=202)


@api_view(["POST"])
@required_request_params(["requestId", "timestamp"])
def health_info_on_request(request):
    request_data = request.data
    print("HIU: Request Received from GW: health_info_on_request", request_data)
    return Response(data={}, status=202)


@api_view(["POST"])
def health_data_receiver(request):
    request_data = request.data
    print("HIU: Health data received Yay!", request.data)
    consent_id = '099b2694-82b4-4934-85e5-188661a417b1'
    decryption_result = _decrypt_health_data(request_data['entries'][0]['content'], request_data['keyMaterial'])
    gw_health_info_notify(consent_id, request_data["transactionId"])

    data = decryption_result['decryptedData']
    data_json = json.loads(data)
    patient = data_json['entry'][2]['resource']['name'][0]['text']
    practitioner = data_json['entry'][1]['resource']['name'][0]['text']
    medication = data_json['entry'][4]['resource']['code']['coding'][0]['display']
    dosage = data_json['entry'][5]['resource']['dosageInstruction'][0]['text']

    import tempfile
    import webbrowser
    from django.template.loader import render_to_string
    html = render_to_string('abdm/health_data.html', {'data': data, 'patient': patient,
                                                      'practitioner': practitioner,
                                                      'medication': medication, 'dosage': dosage})
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html') as f:
        url = 'file://' + f.name
        f.write(html)
    webbrowser.open(url)
    return Response(data={}, status=202)


def _decrypt_health_data(encrypted_health_data, hip_key_material):
    from custom.abdm.poc.encryption_util import decryptData
    decryption_result = decryptData({
        'encryptedData': encrypted_health_data,
        'requesterNonce': key_material['nonce'],
        'senderNonce': hip_key_material['nonce'],
        'requesterPrivateKey': key_material['privateKey'],
        'senderPublicKey': hip_key_material['dhPublicKey']['keyValue']
    })
    print(f"decryption_result: {decryption_result}")
    return decryption_result
