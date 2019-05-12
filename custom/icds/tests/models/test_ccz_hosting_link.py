from __future__ import absolute_import
from __future__ import unicode_literals

import six
from django.test import TestCase
from django.core.exceptions import ValidationError

from corehq.motech.utils import b64_aes_encrypt
from custom.icds.models import CCZHostingLink


class TestCCZHostingLink(TestCase):
    raw_password = "123456"

    def setUp(self):
        super(TestCCZHostingLink, self).setUp()
        self.link = CCZHostingLink(username="user", domain="test", identifier="abcdef")
        self.link.password = b64_aes_encrypt(self.raw_password)

    def test_valid_link(self):
        self.link.full_clean()
        self.link.save()
        self.link.delete()

    def test_identifier_validation(self):
        self.link.identifier = "123-abd"
        with self.assertRaisesMessage(ValidationError, "must be lowercase alphanumeric"):
            self.link.full_clean()

    def test_get_password(self):
        self.assertEqual(self.link.get_password, self.raw_password)

    def test_representation(self):
        self.assertEqual(six.text_type(self.link), self.link.identifier)
