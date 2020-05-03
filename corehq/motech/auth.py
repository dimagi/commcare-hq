import requests
import re
from urllib.parse import urljoin
from requests.exceptions import RequestException


class HTTPBearerAuth(requests.auth.AuthBase):
    def __init__(self, username, plaintext_password):
        self.username = username
        self.password = plaintext_password

    def _find_bearer_base(self, r):
        m = re.compile('https.*/api/v[0-9]+/').match(r.url)
        if m:
            return m.group(0)
        else:
            raise RequestException(None, r, "HTTP endpoint is not not valid for bearer auth")

    def _get_auth_token(self, r):
        token_base = self._find_bearer_base(r)
        token_request_url = urljoin(token_base, "token")

        post_data = {
            "grant_type": "password",
            "username": self.username,
            "password": self.password,
        }

        token_response = requests.post(token_request_url, data=post_data)
        try:
            return token_response.json()['access_token']
        except Exception:
            raise RequestException(
                None, r,
                f"Unable to retrieve access token for request: {token_response.content}"
            )

    def __call__(self, r):
        token = self._get_auth_token(r)
        r.headers["Authorization"] = f"Bearer {token}"
        return r
