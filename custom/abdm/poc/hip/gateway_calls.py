from datetime import datetime, timedelta
import uuid
from custom.abdm.milestone_one.utils.request_util import get_response_http_post

X_CM_ID = 'sbx'     # sandbox consent manager id
PATIENT_ON_SHARE_GW_URL = '/v1.0/patients/profile/on-share'

CARE_CONTEXT_ON_DISCOVER_GW_URL = '/v0.5/care-contexts/on-discover'
CARE_CONTEXT_LINK_ON_INIT_GW_URL = '/v0.5/links/link/on-init'
CARE_CONTEXT_LINK_ON_CONFIRM_GW_URL = '/v0.5/links/link/on-confirm'

CONSENT_ON_NOTIFY_GW_URL = '/v0.5/consents/hip/on-notify'

HEALTH_INFO_ON_REQUEST_GW_URL = '/v0.5/health-information/hip/on-request'
HEALTH_INFO_ON_TRANSFER_GW_URL = '/v0.5/health-information/notify'

ADDITIONAL_HEADERS = {'X-CM-ID': X_CM_ID}

# TODO : Send error if validation fails, remove hard coding for all below calls

# TEMP HARDCODED CONSTS
PATIENT_ID = 'PT-201'
CARE_CONTEXT_ID = 'CC-201'


def gw_patient_profile_on_share(request_id, health_id):
    print("Sending callback request to gateway: gw_patient_profile_on_share")
    data = {
        "requestId": "5f7a535d-a3fd-416b-b069-c97d021fbacd",
        "timestamp": datetime.utcnow().isoformat(),
        "acknowledgement": {
            "status": "SUCCESS",
            "healthId": health_id,
            "tokenNumber": "101"
        },
        # "error": {
        #     "code": 1000,
        #     "message": "Not a valid request"
        # },
        "resp": {
            "requestId": request_id
        }
    }
    get_response_http_post(api_url=PATIENT_ON_SHARE_GW_URL, payload=data,
                           additional_headers=ADDITIONAL_HEADERS)


def gw_care_context_on_discover(request_id, transaction_id):
    print("Sending callback request to gateway: gw_care_context_on_discover")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "transactionId": transaction_id,
        "patient": {
            "referenceNumber": PATIENT_ID,
            "display": "Ajeet",
            "careContexts": [
                {
                    "referenceNumber": CARE_CONTEXT_ID,
                    "display": "Dummy Visit 01 to Ashish Eye Care"
                }
            ],
            "matchedBy": [
                "MOBILE"
            ]
        },
        "resp": {
            "requestId": request_id
        }
    }
    get_response_http_post(api_url=CARE_CONTEXT_ON_DISCOVER_GW_URL, payload=data,
                           additional_headers=ADDITIONAL_HEADERS)


def gw_care_context_link_on_init(request_id, transaction_id):
    print("Sending callback request to gateway: gw_care_context_on_init")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "transactionId": transaction_id,
        "link": {
            "referenceNumber": "LNK-101",
            "authenticationType": "DIRECT",
            "meta": {
                "communicationMedium": "MOBILE",
                "communicationHint": "8291123177",
                "communicationExpiry": (datetime.utcnow() + timedelta(minutes=10)).isoformat()
            }
        },
        "resp": {
            "requestId": request_id
        }
    }
    get_response_http_post(api_url=CARE_CONTEXT_LINK_ON_INIT_GW_URL, payload=data,
                           additional_headers=ADDITIONAL_HEADERS)


def gw_care_context_link_on_confirm(request_id):
    print("Sending callback request to gateway: gw_care_context_on_confirm")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "patient": {
            "referenceNumber": PATIENT_ID,
            "display": "Ajeet",
            "careContexts": [
                {
                    "referenceNumber": CARE_CONTEXT_ID,
                    "display": "Dummy Visit 03 to Ashish Eye Care"
                }
            ]
        },
        "resp": {
            "requestId": request_id
        }
    }
    get_response_http_post(api_url=CARE_CONTEXT_LINK_ON_CONFIRM_GW_URL, payload=data,
                           additional_headers=ADDITIONAL_HEADERS)


def gw_consents_on_notify(request_id, consent_id):
    print("Sending callback request to gateway: gw_consents_on_notify")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "acknowledgement": {
            "status": "OK",
            "consentId": consent_id,
        },
        "resp": {
            "requestId": request_id
        }
    }
    get_response_http_post(api_url=CONSENT_ON_NOTIFY_GW_URL, payload=data,
                           additional_headers=ADDITIONAL_HEADERS)


def gw_health_info_on_request(request_id, transaction_id):
    print("Sending callback request to gateway: gw_health_info_on_request")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "hiRequest": {
            "transactionId": transaction_id,
            "sessionStatus": "ACKNOWLEDGED"
        },
        "resp": {
            "requestId": request_id
        }
    }
    get_response_http_post(api_url=HEALTH_INFO_ON_REQUEST_GW_URL, payload=data,
                           additional_headers=ADDITIONAL_HEADERS)


def gw_health_info_on_transfer(consent_id, transaction_id):
    print("Sending callback request to gateway: gw_health_info_on_transfer")
    data = {
        "requestId": str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "notification": {
            "consentId": consent_id,
            "transactionId": transaction_id,
            "doneAt": datetime.utcnow().isoformat(),
            "notifier": {
                "type": "HIP",
                "id": "6004"
            },
            "statusNotification": {
                "sessionStatus": "TRANSFERRED",
                "hipId": "6004",
                "statusResponses": [
                    {
                        "careContextReference": CARE_CONTEXT_ID,
                        "hiStatus": "DELIVERED",
                        "description": "string"
                    }
                ]
            }
        }
    }
    print(get_response_http_post(api_url=HEALTH_INFO_ON_TRANSFER_GW_URL, payload=data,
                                 additional_headers=ADDITIONAL_HEADERS))
