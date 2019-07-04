from __future__ import absolute_import
from __future__ import unicode_literals

import mock
from django.test import TestCase

from custom.icds.models import (
    HostedCCZ,
    HostedCCZLink,
)
from custom.icds.serializers import HostedCCZSerializer
BUILD = {
    'build_profiles': {
        '12345': {'name': 'Dummy Build Profile'},
    },
}


class TestHostedCCZSerializer(TestCase):
    raw_password = "123456"

    @classmethod
    def setUpClass(cls):
        super(TestHostedCCZSerializer, cls).setUpClass()
        cls.link = HostedCCZLink.objects.create(username="username", password="password",
                                                identifier="link123", domain="test")
        cls.hosted_ccz = HostedCCZ(link=cls.link, app_id="dummy", version=12, profile_id="12345",
                                   file_name="my file")

    @mock.patch('custom.icds.models.get_build_doc_by_version', lambda *args: BUILD)
    def test_data(self):
        self.assertEqual(
            HostedCCZSerializer(self.hosted_ccz, context={'app_names': {
                'dummy': 'Dummy App',
            }}).data,
            {'app_name': 'Dummy App', 'file_name': self.hosted_ccz.file_name,
             'profile_name': 'Dummy Build Profile',
             'app_id': 'dummy',
             'ccz_details': {'name': self.hosted_ccz.file_name,
                             'download_url': '/a/test/ccz/hostings/None/download/'},
             'link_name': self.link.identifier, 'link': self.link.pk, 'version': 12, 'id': None, 'note': ''}
        )

    @classmethod
    def tearDownClass(cls):
        cls.link.delete()
        super(TestHostedCCZSerializer, cls).tearDownClass()
