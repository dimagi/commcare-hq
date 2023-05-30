import requests
from unittest import mock
from django.test import TestCase
from corehq.apps.reports.const import HQ_TABLEAU_GROUP_NAME
from corehq.apps.reports.exceptions import TableauAPIError
from corehq.apps.reports.models import TableauAPISession, TableauConnectedApp, TableauServer


class FakeTableauInstance(mock.MagicMock):

    def __init__(self):
        super(FakeTableauInstance, self).__init__()
        self.groups = {'group1': '1a2b3', 'group2': 'c4d5e', 'group3': 'zx39n', HQ_TABLEAU_GROUP_NAME: 'bn12m'}
        self.users = {'edith@wharton.com': 'zx8cv', 'jeff@company.com': 'uip12', 'george@eliot.com': 'ty78ui'}
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

    def get_group_response(self, group_name):
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
                """ % (self.groups[group_name], group_name))

    def query_groups_response(self):
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
            """ % (self.group_ids[0], self.group_names[0], self.group_ids[1], self.group_names[1],
                   self.group_ids[2], self.group_names[2]))

    def get_users_in_group_response(self):
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
                            "name": "HQ/%s",
                            "siteRole": "Viewer",
                            "locale": "local",
                            "language": "en"
                        },
                        {
                            "externalAuthUserId": "",
                            "id": "%s",
                            "name": "HQ/%s",
                            "siteRole": "Explorer",
                            "locale": "local",
                            "language": "en"
                        }
                    ]
                }
            }
            """ % (self.user_ids[0], self.users_names[0], self.user_ids[2], self.users_names[2]))

    def remove_user_from_group_response(self):
        return self._create_response('')

    def create_group_response(self, name):
        return self._create_response("""
            {
                "group": {
                    "id": "nm12zx",
                    "name": "%s"
                }
            }
        """ % name)

    def add_user_to_group_response(self):
        return self._create_response('')

    def get_groups_for_user_id_response(self):
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

    def update_user_response(self):
        return self._create_response('')

    def delete_user_response(self):
        return self._create_response('')

    def sign_out_response(self):
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


def _setup_test_tableau_server(test_case, domain):
    test_case.test_server = TableauServer(
        domain=domain,
        server_type='server',
        server_name='test_server',
        validate_hostname='host name',
        target_site='target site'
    )
    test_case.test_server.save()
    test_case.connected_app = TableauConnectedApp(
        app_client_id='asdf1234',
        secret_id='zxcv5678',
        server=test_case.test_server
    )
    test_case.connected_app.save()
    test_case.tableau_instance = FakeTableauInstance()


class TestTableauAPISession(TestCase):

    def setUp(self):
        self.domain = 'test-domain-name'
        _setup_test_tableau_server(self, self.domain)
        super(TestTableauAPISession, self).setUp()

    def test_connected_app_encryption(self):
        self.connected_app.plaintext_secret_value = 'qwer1234'
        self.connected_app.save()

        self.assertNotEqual(self.connected_app.encrypted_secret_value, 'qwer1234')
        self.assertEqual(self.connected_app.plaintext_secret_value, 'qwer1234')
        self.assertEqual(len(self.connected_app.encrypted_secret_value), 24)

    def _assert_subset(self, d1, d2):
        self.assertTrue(set(d1.items()).issubset(set(d2.items())))

    @mock.patch('corehq.apps.reports.models.requests.request')
    def _create_session(self, mock_request):
        mock_request.return_value = self.tableau_instance.API_version_response()
        return TableauAPISession(self.connected_app)

    @mock.patch('corehq.apps.reports.models.requests.request')
    def _sign_in(self, mock_request, api_session=None):
        mock_request.return_value = self.tableau_instance.sign_in_response()
        api_session.sign_in()
        return api_session

    @mock.patch('corehq.apps.reports.models.requests.request')
    def _sign_out(self, mock_request, api_session=None):
        mock_request.return_value = self.tableau_instance.sign_out_response()
        api_session.sign_out()
        return api_session

    def test_create_session_and_sign_in(self):
        api_session = self._create_session()
        self._sign_in(api_session=api_session)
        self.assertTrue(api_session.signed_in)
        self.assertEqual(api_session.base_url, 'https://test_server/api/3.15')
        self._assert_subset({'Content-Type': 'application/json'}, api_session.headers)

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_get_group(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        group_1_name = 'group1'
        mock_request.return_value = self.tableau_instance.get_group_response(group_1_name)
        group1 = api_session.get_group(group_1_name)
        self.assertEqual(group1['id'], '1a2b3')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_query_groups(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        mock_request.return_value = self.tableau_instance.query_groups_response()
        groups = api_session.query_groups()
        self.assertEqual(len(groups), 3)
        self.assertEqual(groups[1]['id'], 'c4d5e')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_get_users_in_group(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        mock_request.return_value = self.tableau_instance.get_users_in_group_response()
        users = api_session.get_users_in_group(self.tableau_instance.groups['group1'])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[1]['id'], 'ty78ui')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_create_group(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        name = 'group3'
        mock_request.return_value = self.tableau_instance.create_group_response(name)
        group_id = api_session.create_group(name)
        self.assertEqual(group_id, 'nm12zx')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_add_user_to_group(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        user_id = 'uip12'
        group_id = '1a2b3'
        mock_request.return_value = self.tableau_instance.add_user_to_group_response()
        api_session.add_user_to_group(user_id, group_id)

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_remove_user_from_group(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        user_id = 'uip12'
        group_id = '1a2b3'
        mock_request.return_value = self.tableau_instance.remove_user_from_group_response()
        api_session.remove_user_from_group(user_id, group_id)

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_get_groups_for_user_id(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        mock_request.return_value = self.tableau_instance.get_groups_for_user_id_response()
        jeff_groups = api_session.get_groups_for_user_id('uip12')
        self.assertEqual(len(jeff_groups), 2)
        self.assertEqual(jeff_groups[1]['id'], 'c4d5e')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_create_user(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        username = 'ricardo@company.com'
        role = 'Viewer'
        mock_request.return_value = self.tableau_instance.create_user_response(username, role)
        new_user_id = api_session.create_user(username, role)
        self.assertEqual(new_user_id, 'gh23jk')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_update_user(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        mock_request.side_effect = [self.tableau_instance.delete_user_response(),
                                    self.tableau_instance.create_user_response('jeff@company.com', 'Explorer')]
        new_id = api_session.update_user('uip12', 'Explorer', username='jeff@company.com')
        self.assertEqual(new_id, 'gh23jk')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_delete_user(self, mock_request):
        api_session = self._create_session()
        api_session = self._sign_in(api_session=api_session)
        mock_request.return_value = self.tableau_instance.delete_user_response()
        api_session.delete_user('uip12')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_failure(self, mock_request):
        api_session = self._create_session()
        mock_request.return_value = self.tableau_instance.failure_response()
        self.assertRaises(TableauAPIError, api_session.create_user, 'jamie@company.com', 'Viewer')
