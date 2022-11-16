import requests
from unittest import mock
from django.test import TestCase
from corehq.apps.reports.exceptions import TableauAPIError
from corehq.apps.reports.models import TableauAPISession, TableauConnectedApp, TableauServer


class FakeTableauInstance(mock.MagicMock):

    def __init__(self):
        super(FakeTableauInstance, self).__init__()
        self.groups = {'group1': '1a2b3', 'group2': 'c4d5e'}
        self.users = {'angie@dimagi.com': 'zx8cv', 'jeff@company.com': 'uip12', 'steve@company.com': 'ty78ui'}
        self.group_names = list(self.groups.keys())
        self.group_ids = list(self.groups.values())
        self.users_names = list(self.users.keys())
        self.user_ids = list(self.users.values())

    def _create_response(self, response_text):
        mock_response = requests.Response()
        mock_response.status_code = 200
        mock_response._content = response_text.encode('utf-8')  # Sets the return value for response.text
        return mock_response

    def API_version_response(self):
        return self._create_response("""
        {
            "serverInfo": {
                "productVersion": {
                    "value": "2022.1.5",
                    "build": "20221.22.0823.1450"
                },
                "restApiVersion": "3.15"
            }
        }
        """)

    def sign_in_response(self):
        return self._create_response("""
        {
            "credentials": {
                "site": {
                    "id": "asdfasdf-1234-5678-90as-0s0s0s0s0s0s",
                    "contentUrl": "Test"
                },
                "user": {
                    "id": "123d4567-8901-2e34-5678-9t9t9t9t9t9t"
                },
                "token": "aaaaaaaaaaaaaaaaaaaaaa22222222222222222222222",
                "estimatedTimeToExpiration": "364:00:42"
            }
        }
        """)

    def query_groups_response(self, **kwargs):
        if 'group_name' in kwargs:
            return self._create_response("""
                {
                    "groups": {
                        "group": [
                            {
                                "domain": {
                                    "name": "local"
                                },
                                "id": "%s",
                                "name": "%s"
                            }
                        ]
                    }
                }
                """ % (self.groups[kwargs['group_name']], kwargs['group_name'])
            )
        else:
            return self._create_response("""
                {
                    "pagination": {
                        "pageNumber": "1",
                        "pageSize": "1000",
                        "totalAvailable": "2"
                    },
                    "groups": {
                        "group": [
                            {
                                "domain": {
                                    "name": "local"
                                },
                                "id": "%s",
                                "name": "%s"
                            },
                            {
                                "domain": {
                                    "name": "local"
                                },
                                "id": "%s",
                                "name": "%s"
                            }
                        ]
                    }
                }
                """ % (self.group_ids[0], self.group_names[0], self.group_ids[1], self.group_names[1]))

    def get_users_in_group_response(self, **kwargs):
        return self._create_response("""
            {
                "pagination": {
                    "pageNumber": "1",
                    "pageSize": "100",
                    "totalAvailable": "2"
                },
                "users": {
                    "user": [
                        {
                            "externalAuthUserId": "",
                            "id": "%s",
                            "name": "%s",
                            "siteRole": "Viewer",
                            "locale": "local",
                            "language": "en"
                        },
                        {
                            "externalAuthUserId": "",
                            "id": "%s",
                            "name": "%s",
                            "siteRole": "Explorer",
                            "locale": "local",
                            "language": "en"
                        }
                    ]
                }
            }
            """ % (self.user_ids[0], self.users_names[0], self.user_ids[2], self.users_names[2]))

    def create_group_response(self, **kwargs):
        return self._create_response("""
            {
                "group": {
                    "id": "nm12zx",
                    "name": "%s"
                }
            }
        """ % kwargs['name'])

    def add_user_to_group_response(self, **kwargs):
        return self._create_response('')

    def get_groups_for_user_id_response(self, **kwargs):
        return self._create_response("""
                {
                    "pagination": {
                        "pageNumber": "1",
                        "pageSize": "1000",
                        "totalAvailable": "2"
                    },
                    "groups": {
                        "group": [
                            {
                                "domain": {
                                    "name": "local"
                                },
                                "id": "%s",
                                "name": "%s"
                            },
                            {
                                "domain": {
                                    "name": "local"
                                },
                                "id": "%s",
                                "name": "%s"
                            }
                        ]
                    }
                }
                """ % (self.group_ids[0], self.group_names[0], self.group_ids[1], self.group_names[1]))

    def create_user_response(self, username, role):
        return self._create_response("""
            {
                "user": {
                    "id": "gh23jk",
                    "name": "%s",
                    "siteRole": "%s",
                    "authSetting": "None"
                }
            }
        """ % (username, role))

    def update_user_response(self, **kwargs):
        return self._create_response('')

    def delete_user_response(self, **kwargs):
        return self._create_response('')

    def sign_out_response(self, **kwargs):
        return self._create_response('')

    def failure_response(self):
        response_text = """
            {
                "error": {
                    "summary": "Invalid Authentication Credentials",
                    "detail": "Your authentication credentials are invalid.",
                    "code": "401002"
                }
            }
        """
        mock_response = requests.Response()
        mock_response.status_code = 400
        mock_response._content = response_text.encode('utf-8')
        return mock_response


class TestTableauAPI(TestCase):

    def setUp(self):
        self.domain = 'test-domain-name'
        self.test_server = TableauServer(
            domain=self.domain,
            server_type='server',
            server_name='server name',
            validate_hostname='host name',
            target_site='target site'
        )
        self.test_connected_app = TableauConnectedApp(
            app_client_id='asdf1234',
            secret_id='zxcv5678',
            server=self.test_server
        )
        super(TestTableauConnectedApp, self).setUp()

    def test_encryption(self):
        self.test_connected_app.plaintext_secret_value = 'qwer1234'

        self.assertNotEqual(self.test_connected_app.encrypted_secret_value, 'qwer1234')
        self.assertEqual(self.test_connected_app.plaintext_secret_value, 'qwer1234')
        self.assertEqual(len(self.test_connected_app.encrypted_secret_value), 24)

    def test_jwt(self):
        # Just test that creating the JWT doesn't error out. Tests for actual funcationality of the JWT can be \
        # will be part of Tableau API code.
        jwt = self.test_connected_app.create_jwt()
        self.assertTrue(jwt)
