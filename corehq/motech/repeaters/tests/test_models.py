from django.test import TestCase

from corehq.motech.const import BASIC_AUTH
from corehq.motech.models import ConnectionSettings
from corehq.motech.repeaters.models import FormRepeater
from corehq.motech.repeaters.repeater_generators import (
    FormRepeaterXMLPayloadGenerator,
)

DOMAIN = "greasy-spoon"


class RepeaterConnectionSettingsTests(TestCase):

    def setUp(self):
        self.rep = FormRepeater(
            domain=DOMAIN,
            url="https://spam.example.com/api/",
            auth_type=BASIC_AUTH,
            username="terry",
            password="Don't save me decrypted!",
            notify_addresses_str="admin@example.com",
            format=FormRepeaterXMLPayloadGenerator.format_name,
        )

    def tearDown(self):
        if self.rep.connection_settings_id:
            ConnectionSettings.objects.filter(
                pk=self.rep.connection_settings_id
            ).delete()
        self.rep.delete()

    def test_create_connection_settings(self):
        self.assertIsNone(self.rep.connection_settings_id)
        conn = self.rep.connection_settings

        self.assertIsNotNone(self.rep.connection_settings_id)
        self.assertEqual(conn.name, self.rep.url)
        self.assertEqual(self.rep.plaintext_password, conn.plaintext_password)
        # rep.password was saved decrypted; conn.password is not:
        self.assertNotEqual(self.rep.password, conn.password)
