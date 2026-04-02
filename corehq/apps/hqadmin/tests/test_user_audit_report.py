from django.test import TestCase

from corehq.apps.reports.filters.simple import IPAddressFilter


class TestIPAddressParsing(TestCase):

    def test_single_ip(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.1")
        self.assertEqual(result, [("exact", "192.168.1.1")])

    def test_cidr_32(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.1/32")
        self.assertEqual(result, [("exact", "192.168.1.1")])

    def test_cidr_24(self):
        result = IPAddressFilter.parse_ip_input("192.168.1.0/24")
        self.assertEqual(result, [("startswith", "192.168.1.")])

    def test_cidr_16(self):
        result = IPAddressFilter.parse_ip_input("172.16.0.0/16")
        self.assertEqual(result, [("startswith", "172.16.")])

    def test_cidr_8(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/8")
        self.assertEqual(result, [("startswith", "10.")])

    def test_comma_separated(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/8, 192.168.1.0/24")
        self.assertEqual(result, [
            ("startswith", "10."),
            ("startswith", "192.168.1."),
        ])

    def test_invalid_cidr_suffix(self):
        result = IPAddressFilter.parse_ip_input("10.0.0.0/12")
        self.assertEqual(result, None)

    def test_empty_input(self):
        result = IPAddressFilter.parse_ip_input("")
        self.assertEqual(result, [])

    def test_whitespace_only(self):
        result = IPAddressFilter.parse_ip_input("   ")
        self.assertEqual(result, [])
