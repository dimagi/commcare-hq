import datetime
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


# vaccinator apis
def send_request_to_register_beneficiary_via_vaccinator_api(beneficiary_data):
    if not beneficiary_data:
        beneficiary_data = {
            "name": "Apparao",
            "birth_year": "1980",
            "gender_id": 1,
            "mobile_number": "8383909618",
            "photo_id_type": 1,
            "photo_id_number": "XXXXXXXX9999",
            "consent_version": "1"
        }
    headers = {
        'Accept-Language': 'en_US',
        'User-Agent': '',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

    url = API['vaccinator'] + "vaccinator/beneficiaries/new"
    return requests.post(url, headers=headers, data=json.dumps(beneficiary_data))


def send_request_to_find_beneficiaries_by_mobile_number_via_vaccinator_api(mobile_number):
    if not mobile_number:
        mobile_number = "8383909618"

    headers = {
        'Accept-Language': 'en_US',
        'User-Agent': '',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }

    url = API['vaccinator'] + f"vaccinator/beneficiaries/findByMobile?mobile_number={mobile_number}"
    return requests.get(url, headers=headers)


def send_request_to_notify_vaccination_via_vaccinator_api(vaccination_data):
    if not vaccination_data:
        vaccination_data = {
            "beneficiary_reference_id": "62682606457710",
            "center_id": 563048,
            "vaccine": "COVISHIELD",
            "vaccine_batch": "123456",
            "dose": 1,
            "dose1_date": datetime.date.today().strftime('%d-%m-%Y'),
            "vaccinator_name": "Prabha Devi",
        }

    headers = {
        'Accept-Language': 'en_US',
        'User-Agent': '',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    url = API['vaccinator'] + "vaccinator/beneficiaries/vaccinate"
    return requests.post(url, headers=headers, data=json.dumps(vaccination_data))


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
