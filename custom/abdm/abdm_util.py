import requests
import json

base_url = "https://healthidsbx.abdm.gov.in/api/"


def get_access_token():
    url = "https://dev.abdm.gov.in/gateway/v0.5/sessions"
    payload = {"clientId": "", "clientSecret": ""}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    resp = requests.post(url=url, data=json.dumps(payload), headers=headers)
    if resp.status_code == 200:
        return resp.json().get("accessToken")


def generate_aadhar_otp(aadhaar_number):
    generate_aadhar_otp = "v1/registration/aadhaar/generateOtp"
    payload = {"aadhaar": str(aadhaar_number)}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    print(token)
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    print(resp)
    print(resp.content)
    print(resp.json())
    return resp.json()


def generate_auth_otp(health_id, auth_method):
    url = "https://healthidsbx.abdm.gov.in/api/v2/auth/init"
    payload = {"authMethod": auth_method, "healthid": health_id}
    print(payload)
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    resp = requests.post(url=url, data=json.dumps(payload), headers=headers)
    print(resp.content)
    if resp.status_code == 200:
        return resp.json()


def confirm_with_mobile_otp(otp, txn_id):
    url = "https://healthidsbx.abdm.gov.in/api/v1/auth/confirmWithMobileOTP"
    payload = {"otp": otp, "txnId": txn_id}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    resp = requests.post(url=url, data=json.dumps(payload), headers=headers)
    if resp.status_code == 200:
        return resp.json()


def get_account_information(x_token):
    url = "https://healthidsbx.abdm.gov.in/api/v1/account/profile"
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token), "X-Token": f"Bearer {x_token}"})
    resp = requests.get(url=url, headers=headers)
    if resp.status_code == 200:
        return resp.json()


def generate_mobile_otp(mobile_number, txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/generateMobileOTP"
    payload = {"mobile": str(mobile_number), "txnId": txnid}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    print(token)
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    print(resp)
    print(resp.content)


def verify_aadhar_otp(otp, txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/verifyOTP"
    payload = {"otp": str(otp), "txnId": txnid}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    print(token)
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    print(resp)
    print(resp.content)


def verify_mobile_otp(otp, txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/verifyMobileOTP"
    payload = {"otp": str(otp), "txnId": txnid}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    print(token)
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    print(resp)
    print(resp.content)


def create_health_id(txnid):
    generate_aadhar_otp = "v1/registration/aadhaar/createHealthIdWithPreVerified"
    payload = {
        "email": "",
        "firstName": "",
        "healthId": "",
        "lastName": "",
        "middleName": "",
        "password": "",
        "profilePhoto": "",
        "txnId": txnid
    }
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    print(token)
    resp = requests.post(url=base_url + generate_aadhar_otp, data=json.dumps(payload), headers=headers)
    return resp.json()


def search_by_health_id(health_id):
    url = "https://healthidsbx.abdm.gov.in/api/v1/search/searchByHealthId"
    payload = {"healthId": health_id}
    headers = {"Content-Type": "application/json; charset=UTF-8"}
    token = get_access_token()
    headers.update({"Authorization": "Bearer {}".format(token)})
    print(token)
    resp = requests.post(url=url, data=json.dumps(payload), headers=headers)
    print(resp)
    print(resp.content)
    if resp.status_code == 200:
        return resp.json()
