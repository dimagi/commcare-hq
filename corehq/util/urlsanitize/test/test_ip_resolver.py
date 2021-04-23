from django.test import SimpleTestCase
from socket import AddressFamily, SocketKind
from unittest.mock import patch

from ..ip_resolver import sort_ip_addresses, extract_ip, resolve_ip

INDEX_ADDRESS_FAMILY = 0


class SortIPAddressTests(SimpleTestCase):
    def test_sorts_single_value(self):
        input = [(AddressFamily.AF_INET, SocketKind.SOCK_STREAM, 6, '', ('142.250.64.110', 80))]
        result = sort_ip_addresses(input)
        self.assertEqual(result[0][INDEX_ADDRESS_FAMILY], AddressFamily.AF_INET)

    def test_sorts_ipv4_before_ipv6(self):
        input = [
            (AddressFamily.AF_INET6, SocketKind.SOCK_STREAM, 6, '', ('2607:f8b0:4006:81b::200e', 80)),
            (AddressFamily.AF_INET, SocketKind.SOCK_STREAM, 6, '', ('142.250.64.110', 80)),
            (AddressFamily.AF_INET, SocketKind.SOCK_STREAM, 6, '', ('142.250.64.111', 80)),
        ]
        result = sort_ip_addresses(input)

        self.assertEqual(result[0][INDEX_ADDRESS_FAMILY], AddressFamily.AF_INET)
        self.assertEqual(result[1][INDEX_ADDRESS_FAMILY], AddressFamily.AF_INET)
        self.assertEqual(result[2][INDEX_ADDRESS_FAMILY], AddressFamily.AF_INET6)


class ExtractIPTests(SimpleTestCase):
    def test_extracts_single_ip(self):
        input = (AddressFamily.AF_INET, SocketKind.SOCK_STREAM, 6, '', ('142.250.64.110', 80))
        self.assertEqual(extract_ip(input), '142.250.64.110')


class ResolveIPTests(SimpleTestCase):
    @patch('corehq.util.urlsanitize.ip_resolver.getaddrinfo')
    def test_when_multiple_protocols_prefers_ipv4(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (AddressFamily.AF_INET6, SocketKind.SOCK_STREAM, 6, '', ('2607:f8b0:4006:81b::200e', 80)),
            (AddressFamily.AF_INET, SocketKind.SOCK_STREAM, 6, '', ('142.250.64.110', 80)),
        ]
        self.assertEqual(resolve_ip('test.url'), '142.250.64.110')

    @patch('corehq.util.urlsanitize.ip_resolver.getaddrinfo')
    def test_when_only_ipv6_returns_ipv6(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = [
            (AddressFamily.AF_INET6, SocketKind.SOCK_STREAM, 6, '', ('2607:f8b0:4006:81b::200e', 80)),
        ]
        self.assertEqual(resolve_ip('test.url'), '2607:f8b0:4006:81b::200e')
