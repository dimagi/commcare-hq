# -*- coding: utf-8 -*-
import base64

from django.test import TestCase, override_settings, Client
from django.urls import reverse
from dimagi.utils.couch.cache.cache_core import get_redis_client

from mock import patch

from custom.nic_compliance.utils import (
    extract_password,
    obfuscated_password_redis_key_for_user,
)
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser

OBFUSCATED_PASSWORD_MAPPING = {
    "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127=": "123456",
    "sha256$8f5008c2hhMjU2JDhmNTAwOFlXSmpNVEl6TFE9PTRhNjBhOT0=4a60a9=": "abc123-",
    "sha256$4bf7cdc2hhMjU2JDRiZjdjZE1USXpRQ01rSlRFeTEzMGM4ZD0=130c8d=": "123@#$%12",
    "sha256$29df66c2hhMjU2JDI5ZGY2NklDRkFJeVFsWGlZcUtDbGZLeTFjYTQwN2VkPQ==a407ed=": " !@#$%^&*()_+-\\",
    "sha256$ad5e3ac2hhMjU2JGFkNWUzYTRLU0o0S1NxNEtTVjRLU3c0S1NqTVRJejQyNDgyOT0=424829=": "उपकरण123",
    "sha256$nhiyhsc2hhMjU2JG5oaXloc2FsWmlWVUEvVmxsWk5RPT16eWwzeHU9zyl3xu=": "jVbU@?VYY5"
}


class TestDecodePassword(TestCase):
    username = "username@test.com"

    @classmethod
    def setUpClass(cls):
        super(TestDecodePassword, cls).setUpClass()
        cls.domain = Domain(name="delhi", is_active=True)
        cls.domain.save()
        cls.username = "username@test.com"
        cls.web_user = WebUser.get_by_username(cls.username)
        if cls.web_user:
            cls.web_user.delete()
        cls.web_user = WebUser.create(cls.domain.name, cls.username, "123456")

    @classmethod
    def tearDownClass(cls):
        cls.domain.delete()
        cls.web_user.delete()
        super(TestDecodePassword, cls).tearDownClass()

    def test_no_replay_attack_for_mobile_heartbeat_attempt(self):
        get_redis_client().clear()
        redis_client = get_redis_client()
        with override_settings(OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE=True):
            obfuscated_password = "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
            client = Client(enforce_csrf_checks=False)
            auth_headers = {
                'HTTP_AUTHORIZATION': 'Basic ' + base64.b64encode(
                    ('%s:%s' % (self.username, obfuscated_password)).encode('utf-8')
                ).decode('utf-8'),
            }
            key_name = obfuscated_password_redis_key_for_user(self.username, obfuscated_password)
            self.assertEqual(redis_client.get(key_name), None)
            response = client.get(reverse('phone_heartbeat', args=[self.domain.name, "bad_app_id"]),
                                  **auth_headers)
            self.assertEqual(response.status_code, 404)

            # test no replay attack
            response = client.get(reverse('phone_heartbeat', args=[self.domain.name, "bad_app_id"]),
                                  **auth_headers)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(redis_client.get(key_name), None)

    @patch("custom.nic_compliance.utils.USERS_TO_TRACK_FOR_REPLAY_ATTACK", [username])
    def test_replay_attack_for_mobile_heartbeat_attempt(self):
        get_redis_client().clear()
        redis_client = get_redis_client()
        with override_settings(OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE=True):
            obfuscated_password = "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
            client = Client(enforce_csrf_checks=False)
            auth_headers = {
                'HTTP_AUTHORIZATION': 'Basic ' + base64.b64encode(
                    ('%s:%s' % (self.username, obfuscated_password)).encode('utf-8')
                ).decode('utf-8'),
            }
            # ensure that login attempt gets stored
            key_name = obfuscated_password_redis_key_for_user(self.username, obfuscated_password)
            self.assertFalse(redis_client.get(key_name))
            response = client.get(reverse('phone_heartbeat', args=[self.domain.name, "bad_app_id"]),
                                  **auth_headers)
            self.assertEqual(response.status_code, 404)
            self.assertTrue(redis_client.get(key_name))

            # test replay attack
            response = client.get(reverse('phone_heartbeat', args=[self.domain.name, "bad_app_id"]),
                                  **auth_headers)
            self.assertEqual(response.status_code, 401)
            redis_client.expire(key_name, 0)

    def test_replay_attack_for_web_login_attempt(self):
        get_redis_client().clear()
        redis_client = get_redis_client()
        with override_settings(OBFUSCATE_PASSWORD_FOR_NIC_COMPLIANCE=True):
            obfuscated_password = "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
            client = Client(enforce_csrf_checks=False)
            form_data = {
                'auth-username': self.username,
                'auth-password': obfuscated_password,
                'hq_login_view-current_step': 'auth'
            }
            # ensure that login attempt gets stored
            key_name = obfuscated_password_redis_key_for_user(self.username, obfuscated_password)
            self.assertFalse(redis_client.get(key_name))
            response = client.post(reverse('login'), form_data, follow=True)
            self.assertRedirects(response, '/a/delhi/dashboard/project/')
            self.assertTrue(redis_client.get(key_name))
            client.get(reverse('logout'))

            # test replay attack
            response = client.post(reverse('login'), form_data, follow=True)
            self.assertContains(response, "Please enter a password")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.request['PATH_INFO'], '/accounts/login/')
            redis_client.expire(key_name, 0)


class TestExtractPassword(TestCase):
    def test_password_decoding(self):
        for obfuscated_password, password in OBFUSCATED_PASSWORD_MAPPING.items():
            self.assertEqual(extract_password(obfuscated_password), password)

    def test_invalid_regex_format(self):
        obfuscated_password = "sha255$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
        self.assertEqual(extract_password(obfuscated_password), None)

        obfuscated_password = "sha255$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ=="
        self.assertEqual(extract_password(obfuscated_password), None)

    def test_invalid_padding(self):
        obfuscated_password = "sha256$1e456bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
        self.assertEqual(extract_password(obfuscated_password), '')
