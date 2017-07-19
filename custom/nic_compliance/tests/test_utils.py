# -*- coding: utf-8 -*-
from django.test import TestCase, override_settings, Client
from django.urls import reverse
from dimagi.utils.couch.cache.cache_core import get_redis_client
from custom.nic_compliance.utils import extract_password, verify_password, get_obfuscated_passwords
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser

OBFUSCATED_PASSWORD_MAPPING = {
    "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127=": "123456",
    "sha256$8f5008c2hhMjU2JDhmNTAwOFlXSmpNVEl6TFE9PTRhNjBhOT0=4a60a9=": "abc123-",
    "sha256$4bf7cdc2hhMjU2JDRiZjdjZE1USXpRQ01rSlRFeTEzMGM4ZD0=130c8d=": "123@#$%12",
    "sha256$29df66c2hhMjU2JDI5ZGY2NklDRkFJeVFsWGlZcUtDbGZLeTFjYTQwN2VkPQ==a407ed=": " !@#$%^&*()_+-\\",
    "sha256$ad5e3ac2hhMjU2JGFkNWUzYTRLU0o0S1NxNEtTVjRLU3c0S1NqTVRJejQyNDgyOT0=424829=": u"उपकरण123"
}


class TestDecodePassword(TestCase):
    @classmethod
    def setUpClass(cls):
        super(TestDecodePassword, cls).setUpClass()
        cls.domain = Domain(name="delhi", is_active=True)
        cls.domain.save()
        cls.username = "username@test.com"
        cls.web_user = WebUser.create(cls.domain.name, cls.username, "123456")

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()
        super(TestDecodePassword, cls).tearDownClass()

    def test_login_attempt(self):
        get_redis_client().clear()
        with override_settings(OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE=True):
            obfuscated_password = "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
            client = Client(enforce_csrf_checks=False)
            form_data = {
                'auth-username': self.username,
                'auth-password': obfuscated_password,
                'hq_login_view-current_step': 'auth'
            }
            # ensure that login attempt gets stored
            login_attempts = get_obfuscated_passwords(self.username)
            self.assertEqual(login_attempts, [])
            response = client.post(reverse('login'), form_data, follow=True)
            self.assertRedirects(response, '/a/delhi/dashboard/project/')
            login_attempts = get_obfuscated_passwords(self.username)

            self.assertTrue(
                verify_password(
                    obfuscated_password,
                    login_attempts[0]
                )
            )
            client.get(reverse('logout'))

            # test replay attack
            response = client.post(reverse('login'), form_data, follow=True)
            self.assertContains(response, "Please enter a password")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.request['PATH_INFO'], '/accounts/login/')


class TestExtractPassword(TestCase):
    def test_password_decoding(self):
        for obfuscated_password, password in OBFUSCATED_PASSWORD_MAPPING.items():
            self.assertEqual(extract_password(obfuscated_password), password)

    def test_invalid_regex_format(self):
        obfuscated_password = "sha255$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
        self.assertEqual(extract_password(obfuscated_password), obfuscated_password)

        obfuscated_password = "sha255$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ=="
        self.assertEqual(extract_password(obfuscated_password), obfuscated_password)

    def test_invalid_padding(self):
        obfuscated_password = "sha256$1e456bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
        self.assertEqual(extract_password(obfuscated_password), '')
