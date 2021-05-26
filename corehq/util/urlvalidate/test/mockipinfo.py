from contextlib import contextmanager
from unittest.mock import patch

from corehq.util.urlvalidate.ip_resolver import CannotResolveHost


@contextmanager
def hostname_resolving_to_ips(hostname, ips):
    ip_tuples = [_create_tuple(ip) for ip in ips]
    with patch('socket.getaddrinfo') as mock_getaddrinfo:
        mock_getaddrinfo.side_effect = lambda host, port: ip_tuples if host == hostname else []
        yield


@contextmanager
def unresolvable_hostname(hostname):
    def unresolveable_handler(host, port):
        if host == hostname:
            raise CannotResolveHost(hostname)
        return []
    with patch('socket.getaddrinfo') as mock_getaddrinfo:
        mock_getaddrinfo.side_effect = unresolveable_handler
        yield


def _create_tuple(ip):
    return ('mock_family', 'mock_type', 'mock_proto', 'mock_canonname', (ip, 80))
