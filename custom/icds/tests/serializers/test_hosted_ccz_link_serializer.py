from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import SimpleTestCase

from custom.icds.models import HostedCCZLink
from custom.icds.serializers import HostedCCZLinkSerializer
from custom.nic_compliance.utils import hash_password


class TestHostedCCZLinkSerializer(SimpleTestCase):
    raw_password = "123456"

    def setUp(self):
        super(TestHostedCCZLinkSerializer, self).setUp()
        self.link = HostedCCZLink(username="user", domain="test", identifier="abcdef",
                                  page_title="page title")
        self.link.password = hash_password(self.raw_password)

    def test_data(self):
        self.assertEqual(
            HostedCCZLinkSerializer(self.link).data,
            {'username': 'user', 'identifier': 'abcdef', 'page_title': 'page title', 'id': None}
        )
