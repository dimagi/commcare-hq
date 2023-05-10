from datetime import datetime, timedelta
import uuid
from custom.abdm.milestone_one.utils.request_util import get_response_http_post

X_CM_ID = 'sbx'     # sandbox consent manager id
CONSENT_REQUEST_INIT_GW_URL = '/v0.5/consent-requests/init'
CONSENT_REQUEST_ON_STATUS_GW_URL = '/v0.5/consent-requests/status'
CONSENT_REQUEST_ON_NOTIFY_GW_URL = '/v0.5/consents/hiu/on-notify'

CONSENTS_FETCH_GW_URL = '/v0.5/consents/fetch'

HEALTH_INFO_REQUEST_GW_URL = '/v0.5/health-information/cm/request'
HEALTH_INFO_NOTIFY_GW_URL = '/v0.5/health-information/notify'

ADDITIONAL_HEADERS = {'X-CM-ID': X_CM_ID}

# TODO : Send error if validation fails, remove hard coding for all below calls

# TEMP CONSTS
PATIENT_ABHA_ADDRESS = 'ajeet2050@sbx'
PATIENT_ID = 'PT-201'
CARE_CONTEXT_ID = 'CC-201'
HIP_ID = '6004'
HIU_ID = 'Ashish-HIU-Registered'


def gw_consent_request_init(request_id, patient_abha_address, consent_purpose, health_info_from,
                            health_info_to, health_info_type, consent_expiry):
    print("HIU GW: Consent Request initiation")
    data = {
        "requestId": request_id,
        "timestamp": datetime.utcnow().isoformat(),
        "consent": {
            "purpose": {
                "text": consent_purpose,
                "code": consent_purpose,
                "refUri": "CAREMGT"
            },
            "patient": {
                "id": patient_abha_address
            },
            "hip": {
                "id": HIP_ID
            },
            "careContexts": [
                {
                    "patientReference": PATIENT_ID,
                    "careContextReference": CARE_CONTEXT_ID
                }
            ],
            "hiu": {
                "id": HIU_ID
            },
            "requester": {
                "name": "Dr. Ashish Yogi",
                "identifier": {
                    "type": "REGNO",
                    "value": "MH1001",
                    "system": "https://www.mciindia.org"
                }
            },
            "hiTypes": [health_info_type],
            "permission": {
                "accessMode": "VIEW",
                "dateRange": {
                    "from": health_info_from,
                    "to": health_info_to
                },
                "dataEraseAt": consent_expiry,
                "frequency": {
                    "unit": "HOUR",
                    "value": 1,
                    "repeats": 0
                }
            }
        }
    }
    print(get_response_http_post(api_url=CONSENT_REQUEST_INIT_GW_URL, payload=data,
                                 additional_headers=ADDITIONAL_HEADERS))


def gw_consents_on_notify(request_id, consent_artefacts):
    acknowledgement = [{"status": "OK", "consentId": consent_artefact['id']}
                       for consent_artefact in consent_artefacts]
    print("HIU GW: gw_consents_on_notify")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "acknowledgement": acknowledgement,
        "resp": {
            "requestId": request_id
        }
    }
    get_response_http_post(api_url=CONSENT_REQUEST_ON_NOTIFY_GW_URL, payload=data,
                           additional_headers=ADDITIONAL_HEADERS)


def gw_fetch_consents(consent_id):
    print("HIU GW: Sending consent request to gateway: gw_fetch_consents")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "consentId": consent_id
    }
    print(get_response_http_post(api_url=CONSENTS_FETCH_GW_URL, payload=data,
                                 additional_headers=ADDITIONAL_HEADERS))


def gw_health_info_request(consent_id, hiu_key_material, consent_request):
    print("HIU GW: Sending health info request to gateway: gw_health_info_request")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "hiRequest": {
            "consent": {
                "id": consent_id
            },
            "dateRange": consent_request.details['permission']['dateRange'],
            "dataPushUrl": "http://localhost:8000/abdm/v0.5/health-information/transfer",
            "keyMaterial": hiu_key_material
        }
    }
    print(get_response_http_post(api_url=HEALTH_INFO_REQUEST_GW_URL, payload=data,
                                 additional_headers=ADDITIONAL_HEADERS))


def gw_health_info_notify(consent_id, transaction_id):
    print("HIU GW: Sending callback request to gateway: gw_health_info_on_transfer")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "notification": {
            "consentId": consent_id,
            "transactionId": transaction_id,
            "doneAt": datetime.utcnow().isoformat(),
            "notifier": {
                "type": "HIU",
                "id": HIU_ID
            },
            "statusNotification": {
                "sessionStatus": "TRANSFERRED",
                "hipId": HIP_ID,
                "statusResponses": [
                    {
                        "careContextReference": CARE_CONTEXT_ID,
                        "hiStatus": "OK",
                        "description": "string"
                    }
                ]
            }
        }
    }
    print(get_response_http_post(api_url=HEALTH_INFO_NOTIFY_GW_URL, payload=data,
                                 additional_headers=ADDITIONAL_HEADERS))
