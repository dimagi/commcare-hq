import json
import requests


API = {
    'public': 'https://cdn-api.co-vin.in/api/v2/',
    'protected': 'https://cdndemo-api.co-vin.in/api/v2/',
    'vaccinator': 'https://cdndemo-api.co-vin.in/api/v2/'
}


API_KEYS = {
    'protected': '3sjOr2rmM52GzhpMHjDEE1kpQeRxwFDr4YcBEimi',
}


# public apis
def send_request_for_meta_beneficiary_via_public_api():
    headers = {
        'Accept-Language': 'en_US',
        'User-Agent': '',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

    url = API['public'] + "registration/beneficiary/idTypes"
    return requests.get(url, headers=headers)


# protected apis
def send_request_for_otp_via_protected_api(mobile_number):
    if not mobile_number:
        mobile_number = "8383909618"

    data = {
        'mobile': mobile_number
    }

    headers = {
        'Accept-Language': 'en_US',
        'User-Agent': '',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Api-Key': API_KEYS['protected'],

    }

    url = API['protected'] + "auth/generateOTP"
    return requests.post(url, headers=headers, data=json.dumps(data))


def send_request_to_confirm_otp_via_protected_api(otp, txn_id):
    data = {
        'otp': otp,
        'txnId': txn_id
    }

    headers = {
        'Accept-Language': 'en_US',
        'User-Agent': '',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Api-Key': API_KEYS['protected'],
    }

    url = API['protected'] + "auth/confirmOTP"
    return requests.post(url, headers=headers, data=json.dumps(data))


def send_request_to_register_beneficiary_via_protected_api(token, beneficiary_data):
    if not beneficiary_data:
        beneficiary_data = {
            "name": "Apparao",
            "birth_year": "1980",
            "gender_id": 1,
            "photo_id_type": 1,
            "photo_id_number": "XXXXXXXX9999",
            "comorbidity_ind": "Y",
            "consent_version": "1"
        }

    headers = {
        'Accept-Language': 'en_US',
        'User-Agent': '',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'X-Api-Key': API_KEYS['protected'],
        'Authorization': f'Bearer {token}',
    }

    url = API['protected'] + "registration/beneficiary/new"
    return requests.post(url, headers=headers, data=json.dumps(beneficiary_data))
