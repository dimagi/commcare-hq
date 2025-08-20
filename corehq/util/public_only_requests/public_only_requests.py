import requests
from requests.adapters import HTTPAdapter


def get_public_only_session(domain_name, src):
    session = requests.Session()
    make_session_public_only(session, domain_name, src)
    return session


def make_session_public_only(session, domain_name, src):
    """
    Modifies `session` to validate urls before sending and accept only hosts resolving to public IPs

    Once this function has been called on a session, session.request, etc., will
    raise PossibleSSRFAttempt whenever called with a url host that resolves to a non-public IP.
    """
    # the following two lines entirely replace the default adapters with our custom ones
    # by redefining the adapter to use for the two default prefixes
    session.mount('http://', PublicOnlyHttpAdapter(domain_name=domain_name, src=src))
    session.mount('https://', PublicOnlyHttpAdapter(domain_name=domain_name, src=src))


class PublicOnlyHttpAdapter(HTTPAdapter):
    def __init__(self, domain_name, src):
        self.domain_name = domain_name
        self.src = src
        super().__init__()

    def get_connection_with_tls_context(self, request, verify, proxies=None, cert=None):
        from corehq.motech.requests import validate_user_input_url_for_repeaters
        validate_user_input_url_for_repeaters(request.url, domain=self.domain_name, src=self.src)
        return super().get_connection_with_tls_context(request, verify, proxies, cert)
