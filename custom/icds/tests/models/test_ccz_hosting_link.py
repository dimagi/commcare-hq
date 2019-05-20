from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase
from django.core.exceptions import ValidationError

from custom.icds.models import CCZHostingLink
from custom.nic_compliance.utils import verify_password


class TestCCZHostingLink(TestCase):
    raw_password = "123456"

    def setUp(self):
        super(TestCCZHostingLink, self).setUp()
        self.link = CCZHostingLink(username="user", domain="test", identifier="abcdef",
                                   password=self.raw_password)

    def tearDown(self):
        if self.link.pk:
            self.link.delete()

    def test_valid_link(self):
        self.link.full_clean()
        self.link.save()

    def test_identifier_validation(self):
        self.link.identifier = "123-abd"
        with self.assertRaisesMessage(ValidationError, "must be lowercase alphanumeric"):
            self.link.full_clean()

    def test_encrypted_password(self):
        self.link.save()
        self.assertNotEqual(self.link.password, self.raw_password)
        self.assertTrue(verify_password(self.raw_password, self.link.password),
                        "encrypted password does not match")
