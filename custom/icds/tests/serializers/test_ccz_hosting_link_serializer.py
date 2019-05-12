from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import SimpleTestCase

from custom.icds.models import CCZHostingLink
from custom.icds.serializers import CCZHostingLinkSerializer
from custom.nic_compliance.utils import hash_password


class TestCCZHostingLinkSerializer(SimpleTestCase):
    raw_password = "123456"

    def setUp(self):
        super(TestCCZHostingLinkSerializer, self).setUp()
        self.link = CCZHostingLink(username="user", domain="test", identifier="abcdef",
                                   page_title="page title")
        self.link.password = hash_password(self.raw_password)

    def test_data(self):
        self.assertEqual(
            CCZHostingLinkSerializer(self.link).data,
            {'username': 'user', 'identifier': 'abcdef', 'page_title': 'page title', 'id': None}
        )
