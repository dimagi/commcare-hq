from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import SimpleTestCase

from corehq.motech.utils import b64_aes_encrypt
from custom.icds.models import CCZHostingLink
from custom.icds.serializers import CCZHostingLinkSerializer


class TestCCZHostingLinkSerializer(SimpleTestCase):
    raw_password = "123456"

    def setUp(self):
        super(TestCCZHostingLinkSerializer, self).setUp()
        self.link = CCZHostingLink(username="user", domain="test", identifier="abcdef",
                                   page_title="page title")
        self.link.password = b64_aes_encrypt(self.raw_password)

    def test_data(self):
        self.assertEqual(
            CCZHostingLinkSerializer(self.link).data,
            {'username': 'user', 'identifier': 'abcdef', 'page_title': 'page title', 'id': None}
        )
