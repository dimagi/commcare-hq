from datetime import datetime

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.es.tests.utils import es_test, populate_user_index
from corehq.apps.users.bulk_download import parse_web_users
from corehq.apps.users.models import Invitation, SQLUserRole, WebUser
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.util.elastic import ensure_index_deleted


@es_test
class TestDownloadWebUsers(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'old_shelf'
        cls.domain_obj = create_domain(cls.domain)

        cls.role = SQLUserRole.create(domain=cls.domain, name='App Editor')
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

        cls.other_role = SQLUserRole.create(domain=cls.domain, name='User Admin')

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

        populate_user_index([
            cls.user1.to_json(),
            cls.user2.to_json(),
            cls.user10.to_json(),
            cls.user11.to_json(),
        ])

    @classmethod
    def tearDownClass(cls):
        ensure_index_deleted(USER_INDEX)
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
