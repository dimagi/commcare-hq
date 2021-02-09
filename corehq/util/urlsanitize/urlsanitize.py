import socket
import ipaddress
from urllib.parse import urlparse


def sanitize_user_input_url(url):
    """
    Return ip address if the url is safe to make user-driven requests against

    raise PossibleSSRFAttempt if the url resolves to a non-public ip address
    raise CannotResolveHost if the url host does not resolve
    """
    parsed_url = urlparse(url)
    hostname = parsed_url.hostname
    scheme = parsed_url.scheme
    if hostname is None:
        raise InvalidURL()
    if scheme not in ['http', 'https']:
        raise PossibleSSRFAttempt('scheme not http(s)')
    try:
        ip_address_text = socket.gethostbyname(hostname)
    except socket.gaierror:
        raise CannotResolveHost()
    ip_address = ipaddress.ip_address(ip_address_text)
    return sanitize_ip(ip_address)


def sanitize_ip(ip_address):
    if ip_address.is_loopback:
        raise PossibleSSRFAttempt('is_loopback')
    elif ip_address.is_reserved:
        raise PossibleSSRFAttempt('is_reserved')
    elif ip_address.is_link_local:
        raise PossibleSSRFAttempt('is_link_local')
    elif ip_address.is_multicast:
        raise PossibleSSRFAttempt('is_multicast')
    elif ip_address.is_private:
        raise PossibleSSRFAttempt('is_private')
    elif not ip_address.is_global:
        raise PossibleSSRFAttempt('not is_global')
    else:
        return ip_address


class PossibleSSRFAttempt(Exception):
    def __init__(self, reason):
        super().__init__("Invalid URL")
        self.reason = reason


class CannotResolveHost(Exception):
    pass


class InvalidURL(Exception):
    pass
