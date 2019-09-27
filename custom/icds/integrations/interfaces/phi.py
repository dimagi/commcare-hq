from django.conf import settings

from custom.icds.integrations.clients.phi import PHIApiClient
from custom.icds.integrations.interfaces.exceptions.phi import (
    AuthenticationFailure,
    MissingCredentials,
)


class BasePHIInterface(object):
    client_type = None

    def __init__(self):
        self._response = None
        self._ensure_credentials()

    def _ensure_credentials(self):
        if not self._api_key or not self._password:
            raise MissingCredentials("Please set api key and password for phi")

    @property
    def _data(self):
        raise NotImplementedError

    def send_request(self):
        self._response = self._client.send_request()
        if self._response.status_code == 403:
            raise AuthenticationFailure("Authentication Failed")
        return self._parse_response()

    @property
    def _client(self):
        return PHIApiClient(
            self._api_key, self._password, self.client_type, self._data
        )

    @property
    def _api_key(self):
        return settings.PHI_API_KEY

    @property
    def _password(self):
        return settings.PHI_PASSWORD

    def _parse_response(self):
        return self._response.json()


class SearchBeneficiary(BasePHIInterface):
    client_type = 'search'

    def __init__(self, beneficiary_details):
        super(SearchBeneficiary, self).__init__()
        self.beneficiary_details = beneficiary_details

    @property
    def _data(self):
        return self.beneficiary_details


class GetBeneficiary(BasePHIInterface):
    client_type = 'get'

    def __init__(self, phi_id):
        super(GetBeneficiary, self).__init__()
        self.phi_id = phi_id

    @property
    def _data(self):
        return {
            'phi_id': self.phi_id
        }


class ValidatePHI(BasePHIInterface):
    client_type = 'validate'

    def __init__(self, phi_id):
        super(ValidatePHI, self).__init__()
        self.phi_id = phi_id

    @property
    def _data(self):
        return {
            'phi_id': self.phi_id
        }

    def _parse_response(self):
        json_response = super(ValidatePHI, self)._parse_response()
        if 'result' in json_response and json_response['result'] == 'true':
            return True
        return False
