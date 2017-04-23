# -*- coding: utf-8 -*-
from django.test import TestCase, override_settings
from django.contrib.auth.hashers import get_hasher

from corehq.apps.hqwebapp.models import HashedPasswordLoginAttempt
from corehq.apps.hqwebapp.utils import decode_password, extract_password

HASHED_PASSWORD_MAPPING = {
    "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127=": "123456",
    "sha256$8f5008c2hhMjU2JDhmNTAwOFlXSmpNVEl6TFE9PTRhNjBhOT0=4a60a9=": "abc123-",
    "sha256$4bf7cdc2hhMjU2JDRiZjdjZE1USXpRQ01rSlRFeTEzMGM4ZD0=130c8d=": "123@#$%12",
    "sha256$29df66c2hhMjU2JDI5ZGY2NklDRkFJeVFsWGlZcUtDbGZLeTFjYTQwN2VkPQ==a407ed=": " !@#$%^&*()_+-\\",
    "sha256$ad5e3ac2hhMjU2JGFkNWUzYTRLU0o0S1NxNEtTVjRLU3c0S1NqTVRJejQyNDgyOT0=424829=": u"उपकरण123"
}


@override_settings(ENABLE_PASSWORD_HASHING=True)
class TestDecodePassword(TestCase):
    def test_decoder(self):
        hasher = get_hasher()
        for password_hash, password in HASHED_PASSWORD_MAPPING.items():
            HashedPasswordLoginAttempt.objects.all().delete()
            self.assertEqual(decode_password(password_hash, "username"), password)
            self.assertTrue(
                hasher.verify(
                    password_hash,
                    HashedPasswordLoginAttempt.objects.filter(username="username").all()[0].password_hash
                )
            )

    def test_replay_attack(self):
        password_hash = "sha256$1e2d5bc2hhMjU2JDFLMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
        hasher = get_hasher()
        username = "james@007.com"
        HashedPasswordLoginAttempt.objects.create(
            username=username,
            password_hash=hasher.encode(password_hash, hasher.salt())
        )
        self.assertEqual(decode_password(password_hash, username), '')


class TestExtractPassword(TestCase):
    def test_invalid_regex_format(self):
        password_hash = "sha255$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
        self.assertEqual(extract_password(password_hash), password_hash)

        password_hash = "sha255$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ=="
        self.assertEqual(extract_password(password_hash), password_hash)

    def test_invalid_padding(self):
        password_hash = "sha256$1e456bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127="
        self.assertEqual(extract_password(password_hash), '')
