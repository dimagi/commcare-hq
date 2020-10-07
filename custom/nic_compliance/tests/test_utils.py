from django.test import TestCase

from custom.nic_compliance.utils import extract_password

OBFUSCATED_PASSWORD_MAPPING = {
    "sha256$1e2d5bc2hhMjU2JDFlMmQ1Yk1USXpORFUyZjc5MTI3PQ==f79127=": "123456",
    "sha256$8f5008c2hhMjU2JDhmNTAwOFlXSmpNVEl6TFE9PTRhNjBhOT0=4a60a9=": "abc123-",
    "sha256$4bf7cdc2hhMjU2JDRiZjdjZE1USXpRQ01rSlRFeTEzMGM4ZD0=130c8d=": "123@#$%12",
    "sha256$29df66c2hhMjU2JDI5ZGY2NklDRkFJeVFsWGlZcUtDbGZLeTFjYTQwN2VkPQ==a407ed=": " !@#$%^&*()_+-\\",
    "sha256$ad5e3ac2hhMjU2JGFkNWUzYTRLU0o0S1NxNEtTVjRLU3c0S1NqTVRJejQyNDgyOT0=424829=": "उपकरण123",
    "sha256$nhiyhsc2hhMjU2JG5oaXloc2FsWmlWVUEvVmxsWk5RPT16eWwzeHU9zyl3xu=": "jVbU@?VYY5"
}


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
