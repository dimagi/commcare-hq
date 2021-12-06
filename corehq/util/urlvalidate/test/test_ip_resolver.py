from ipaddress import IPv4Address, IPv6Address
from socket import AddressFamily, SocketKind

from django.test import SimpleTestCase

from ..ip_resolver import extract_ip, resolve_to_ips
from .mockipinfo import hostname_resolving_to_ips

INDEX_ADDRESS_FAMILY = 0


class ExtractIPTests(SimpleTestCase):
    def test_extracts_single_ip(self):
        input = (AddressFamily.AF_INET, SocketKind.SOCK_STREAM, 6, '', ('142.250.64.110', 80))
        self.assertEqual(extract_ip(input), IPv4Address('142.250.64.110'))

    def test_extracts_ipv6_ip(self):
        input = (AddressFamily.AF_INET6, SocketKind.SOCK_STREAM, 6, '', ('2607:f8b0:4006:81b::200e', 80))
        self.assertEqual(extract_ip(input), IPv6Address('2607:f8b0:4006:81b::200e'))


class ResolveToIPsTests(SimpleTestCase):
    def test_preserves_order_of_results(self):
        with hostname_resolving_to_ips('test.url', ['192.168.0.1', '2607:f8b0:4006:81b::200e', '142.250.64.110']):
            self.assertEqual(
                resolve_to_ips('test.url'),
                [
                    IPv4Address('192.168.0.1'),
                    IPv6Address('2607:f8b0:4006:81b::200e'),
                    IPv4Address('142.250.64.110')
                ]
            )
