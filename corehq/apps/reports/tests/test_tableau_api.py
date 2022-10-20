from django.test import TestCase
from corehq.apps.reports.models import TableauConnectedApp, TableauServer


class TestTableauConnectedApp(TestCase):

    def setUp(self):
        self.domain = 'test-domain-name'
        self.test_server = TableauServer(
            domain=self.domain,
            server_type='server',
            server_name='server name',
            validate_hostname='host name',
            target_site='target site'
        )
        self.test_server.save()
        self.test_connected_app = TableauConnectedApp(
            app_client_id='asdf1234',
            secret_id='zxcv5678',
            server=self.test_server
        )
        self.test_connected_app.save()
        super(TestTableauConnectedApp, self).setUp()

    def test_encryption(self):
        self.test_connected_app.plaintext_secret_value = 'qwer1234'
        self.test_connected_app.save()

        self.assertNotEqual(self.test_connected_app.encrypted_secret_value, 'qwer1234')
        self.assertEqual(self.test_connected_app.plaintext_secret_value, 'qwer1234')
        self.assertEqual(len(self.test_connected_app.encrypted_secret_value), 24)

    def test_jwt(self):
        # Just test that creating the JWT doesn't error out. Tests for actual funcationality of the JWT can be \
        # will be part of Tableau API code.
        jwt = self.test_connected_app.create_jwt()
        self.assertTrue(jwt)
