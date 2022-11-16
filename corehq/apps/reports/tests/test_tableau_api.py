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
            server_name='test_server',
            validate_hostname='host name',
            target_site='target site'
        )
        self.test_server.save()
        self.connected_app = TableauConnectedApp(
            app_client_id='asdf1234',
            secret_id='zxcv5678',
            server=self.test_server
        )
        self.connected_app.save()
        self.tableau_instance = FakeTableauInstance()
        super(TestTableauAPI, self).setUp()

    def test_connected_app_encryption(self):
        self.connected_app.plaintext_secret_value = 'qwer1234'
        self.connected_app.save()

        self.assertNotEqual(self.connected_app.encrypted_secret_value, 'qwer1234')
        self.assertEqual(self.connected_app.plaintext_secret_value, 'qwer1234')
        self.assertEqual(len(self.connected_app.encrypted_secret_value), 24)

    def _assert_subset(self, d1, d2):
        self.assertTrue(set(d1.items()).issubset(set(d2.items())))

    def test_tableau_API_session(self):

        self._API_method(method='create_session')
        self.assertFalse(self.api_session.signed_in)
        self.assertEqual(self.api_session.base_url, 'https://test_server/api/3.15')
        self._assert_subset({'Content-Type': 'application/json'}, self.api_session.headers)

        self._API_method(method='sign_in')
        self.assertTrue(self.api_session.signed_in)
        self.assertEqual(self.api_session.site_id, 'asdfasdf-1234-5678-90as-0s0s0s0s0s0s')
        self._assert_subset({'X-Tableau-Auth': 'aaaaaaaaaaaaaaaaaaaaaa22222222222222222222222'},
                            self.api_session.headers)

        group1 = self._API_method(method='query_groups', group_name='group1')
        self.assertEqual(group1['id'], '1a2b3')
        groups = self._API_method(method='query_groups')
        self.assertEqual(len(groups), 2)
        self.assertEqual(groups[1]['id'], 'c4d5e')

        users = self._API_method(method='get_users_in_group', group_id=self.tableau_instance.groups['group1'])
        self.assertEqual(len(users), 2)
        self.assertEqual(users[1]['id'], 'ty78ui')

        group_id = self._API_method(method='create_group', name='group3', min_site_role='Viewer')
        self.assertEqual(group_id, 'nm12zx')

        self._API_method(method='add_user_to_group', user_id='uip12', group_id='1a2b3')

        jeff_groups = self._API_method(method='get_groups_for_user_id', id='uip12')
        self.assertEqual(len(jeff_groups), 2)
        self.assertEqual(jeff_groups[1]['id'], 'c4d5e')

        new_user_id = self._API_method(method="create_user", username='ricardo@company.com', role='Viewer')
        self.assertEqual(new_user_id, 'gh23jk')

        self._API_method(method="update_user", id='uip12', role='Explorer')
        self._API_method(method="delete_user", id='uip12')

        self._API_method(method="sign_out", id='uip12')
        self.assertFalse(self.api_session.signed_in)

        self._test_failure()

    @mock.patch('corehq.apps.reports.models.requests.request')
    def _API_method(self, mock_request, method=None, **kwargs):
        if method == 'create_session':
            mock_request.return_value = self.tableau_instance.API_version_response()
            self.api_session = TableauAPISession(self.connected_app)
        elif method == 'sign_in':
            mock_request.return_value = self.tableau_instance.sign_in_response()
            self.api_session.sign_in()
        elif method == 'query_groups':
            mock_request.return_value = self.tableau_instance.query_groups_response(**kwargs)
            return self.api_session.query_groups(kwargs['group_name'] if 'group_name' in kwargs else None)
        elif method == 'get_users_in_group':
            mock_request.return_value = self.tableau_instance.get_users_in_group_response(**kwargs)
            return self.api_session.get_users_in_group(kwargs['group_id'])
        elif method == 'create_group':
            mock_request.return_value = self.tableau_instance.create_group_response(**kwargs)
            return self.api_session.create_group(kwargs['name'], kwargs['min_site_role'])
        elif method == 'add_user_to_group':
            mock_request.return_value = self.tableau_instance.add_user_to_group_response(**kwargs)
            return self.api_session.add_user_to_group(kwargs['user_id'], kwargs['group_id'])
        elif method == 'get_groups_for_user_id':
            mock_request.return_value = self.tableau_instance.get_groups_for_user_id_response(**kwargs)
            return self.api_session.get_groups_for_user_id(kwargs['id'])
        elif method == 'create_user':
            mock_request.return_value = self.tableau_instance.create_user_response(**kwargs)
            return self.api_session.create_user(kwargs['username'], kwargs['role'])
        elif method == 'update_user':
            mock_request.return_value = self.tableau_instance.update_user_response(**kwargs)
            return self.api_session.update_user(kwargs['id'], kwargs['role'])
        elif method == 'delete_user':
            mock_request.return_value = self.tableau_instance.delete_user_response(**kwargs)
            return self.api_session.delete_user(kwargs['id'])
        elif method == 'sign_out':
            mock_request.return_value = self.tableau_instance.sign_out_response()
            self.api_session.sign_out()
        else:
            raise Exception('API method not tested.')

    @mock.patch('corehq.apps.reports.models.requests.request')
    def _test_failure(self, mock_request):
        mock_request.return_value = self.tableau_instance.failure_response()
        self.assertRaises(TableauAPIError, self.api_session.create_user, 'jamie@company.com', 'Viewer')
