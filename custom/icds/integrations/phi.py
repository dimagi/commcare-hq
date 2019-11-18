import json

from django.conf import settings

import requests

from custom.icds.integrations.const import PHI_URLS as URLS
from custom.icds.integrations.exceptions.phi import (
    AuthenticationFailure,
    MissingCredentials,
    UnexpectedRequest,
)


def send_request(request_type, data):
    if isinstance(data, dict):
        data = json.dumps(data)
    if request_type not in URLS:
        raise UnexpectedRequest("Unexpected request type %s" % request_type)
    password = settings.PHI_PASSWORD
    apikey = settings.PHI_API_KEY
    if not password or not apikey:
        raise MissingCredentials("Please set api key and password for phi")
    response = requests.post(
        URLS[request_type],
        data=data,
        headers={
            'Authorization': 'Basic %s' % password,
            'apikey': apikey,
            'content-type': 'application/json'
        }
    )
    if response.status_code == 403:
        raise AuthenticationFailure("Authentication Failed")
    return response
