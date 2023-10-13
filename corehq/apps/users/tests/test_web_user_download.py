from datetime import datetime
from unittest import mock

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test, populate_user_index
from corehq.apps.es.users import user_adapter
from corehq.apps.users.bulk_download import parse_web_users
from corehq.apps.users.models import Invitation, UserRole, WebUser
from corehq.apps.reports.models import TableauUser
from corehq.apps.reports.tests.test_tableau_api_session import _setup_test_tableau_server
from corehq.apps.reports.tests.test_tableau_api_util import _mock_create_session_responses
from corehq.util.test_utils import disable_quickcache, flag_enabled


@es_test(requires=[user_adapter], setup_class=True)
class TestDownloadWebUsers(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'old_shelf'
        cls.domain_obj = create_domain(cls.domain)

        cls.role = UserRole.create(domain=cls.domain, name='App Editor')
        cls.qualified_role_id = cls.role.get_qualified_id()

        cls.user1 = WebUser.create(
            cls.domain_obj.name,
            'edith@wharton.com',
            'badpassword',
            None,
            None,
            email='edith@wharton.com',
            first_name='Edith',
            last_name='Wharton',
            role_id=cls.role.get_id,
        )

        cls.user2 = WebUser.create(
            cls.domain_obj.name,
            'george@eliot.com',
            'anotherbadpassword',
            None,
            None,
            email='george@eliot.com',
            first_name='George',
            last_name='Eliot',
            is_admin=True,
        )

        cls.invited_user = Invitation.objects.create(
            email='invited_to_domain@user.com',
            domain=cls.domain_obj.name,
            invited_by='tester@test.com',
            invited_on=datetime.utcnow(),
            role=cls.qualified_role_id,
        )

        cls.other_domain = 'new_shelf'
        cls.other_domain_obj = create_domain(cls.other_domain)

        cls.other_role = UserRole.create(domain=cls.domain, name='User Admin')

        cls.user10 = WebUser.create(
            cls.other_domain_obj.name,
            'susan@choi.com',
            'secret',
            None,
            None,
            email='susan@choi.com',
            first_name='Susan',
            last_name='Choi',
            role_id=cls.other_role.get_id,
        )

        cls.user11 = WebUser.create(
            cls.other_domain_obj.name,
            'zadie@smith.com',
            'secret',
            None,
            None,
            email='zadie@smith.com',
            first_name='Zadie',
            last_name='Smith',
            role_id=cls.other_role.get_id,
        )

        cls.other_invited_user = Invitation.objects.create(
            email='invited_to_other_domain@user.com',
            domain=cls.other_domain_obj.name,
            invited_by='tester@test.com',
            invited_on=datetime.utcnow(),
            role=cls.other_role.get_qualified_id()
        )

        populate_user_index([cls.user1, cls.user2, cls.user10, cls.user11])

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete(cls.domain_obj.name, deleted_by=None)
        cls.user2.delete(cls.domain_obj.name, deleted_by=None)
        cls.user10.delete(cls.other_domain_obj.name, deleted_by=None)
        cls.user11.delete(cls.other_domain_obj.name, deleted_by=None)
        cls.invited_user.delete()
        cls.other_invited_user.delete()
        cls.domain_obj.delete()
        cls.other_domain_obj.delete()
        cls.role.delete()
        cls.other_role.delete()
        super().tearDownClass()

    def test_download(self):
        (headers, rows) = parse_web_users(self.domain_obj.name, {})

        rows = list(rows)
        self.assertEqual(3, len(rows))

        spec = dict(zip(headers, rows[0]))
        self.assertEqual('Edith', spec['first_name'])
        self.assertEqual('Wharton', spec['last_name'])
        self.assertEqual('edith@wharton.com', spec['username'])
        self.assertEqual('edith@wharton.com', spec['email'])
        self.assertEqual('App Editor', spec['role'])
        self.assertEqual('Active User', spec['status'])

        spec = dict(zip(headers, rows[1]))
        self.assertEqual('Admin', spec['role'])

        spec = dict(zip(headers, rows[2]))
        self.assertEqual('invited_to_domain@user.com', spec['username'])
        self.assertEqual('invited_to_domain@user.com', spec['email'])
        self.assertEqual('App Editor', spec['role'])
        self.assertEqual('Invited', spec['status'])

    def test_search_string(self):
        (headers, rows) = parse_web_users(self.domain_obj.name, {"search_string": "Edith"})
        rows = list(rows)
        self.assertEqual(1, len(rows))

        spec = dict(zip(headers, rows[0]))
        self.assertEqual('Edith', spec['first_name'])

    def test_multi_domain_download(self):
        (headers, rows) = parse_web_users(self.domain_obj.name, {"domains": [self.domain, self.other_domain]})

        rows = list(rows)
        self.assertEqual(6, len(rows))

        rows = [dict(zip(headers, row)) for row in rows]
        self.assertEqual({(r["username"], r["domain"]) for r in rows}, {
            ("edith@wharton.com", self.domain),
            ("george@eliot.com", self.domain),
            ("invited_to_domain@user.com", self.domain),
            ("zadie@smith.com", self.other_domain),
            ("susan@choi.com", self.other_domain),
            ("invited_to_other_domain@user.com", self.other_domain),
        })

    def _setup_tableau_users(self):
        _setup_test_tableau_server(self, self.domain)
        TableauUser.objects.create(
            server=self.connected_app.server,
            username='edith@wharton.com',
            role=TableauUser.Roles.VIEWER.value)
        TableauUser.objects.create(
            server=self.connected_app.server,
            username='george@eliot.com',
            role=TableauUser.Roles.EXPLORER.value)

    @flag_enabled('TABLEAU_USER_SYNCING')
    @disable_quickcache
    @mock.patch('corehq.apps.reports.models.requests.request')
    def test_tableau_user_download(self, mock_request):
        self._setup_tableau_users()
        mock_request.side_effect = _mock_create_session_responses(self) + [
            self.tableau_instance.query_groups_response(),
            self.tableau_instance.get_users_in_group_response(),
            self.tableau_instance.get_users_in_group_response(),
            self.tableau_instance.get_users_in_group_response()
        ] + _mock_create_session_responses(self) + [
            self.tableau_instance.query_groups_response(),
            self.tableau_instance.failure_response()
        ]
        (headers, rows) = parse_web_users(self.domain_obj.name, {})

        rows = list(rows)
        self.assertEqual(3, len(rows))

        spec = dict(zip(headers, rows[0]))
        self.assertEqual(TableauUser.Roles.VIEWER.value, spec['tableau_role'])
        self.assertEqual("group1,group2,group3",
            spec['tableau_groups'])

        spec = dict(zip(headers, rows[1]))
        self.assertEqual(TableauUser.Roles.EXPLORER.value, spec['tableau_role'])

        (headers, rows) = parse_web_users(self.domain_obj.name, {})
        spec = dict(zip(headers, list(rows)[0]))
        # Should be ERROR since the second get_groups_for_user_id response fails
        self.assertEqual('ERROR', spec['tableau_groups'])
