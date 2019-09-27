from django.utils.functional import cached_property

import requests

from custom.icds.integrations.const import PHI_URLS as URLS


class PHIApiClient(object):
    def __init__(self, apikey, password, request_type, data):
        self.apikey = apikey
        self.password = password
        self.request_type = request_type
        self.data = data

    @cached_property
    def _headers(self):
        return {
            'Authorization': 'Basic {}' % self.password,
            'apikey': self.apikey,
            'content-type': 'application/json'
        }

    def send_request(self):
        return requests.post(
            URLS[self.request_type],
            data=self.data,
            headers=self._headers
        )
