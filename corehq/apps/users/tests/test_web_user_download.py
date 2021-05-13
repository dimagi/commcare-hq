from datetime import datetime

from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser, Invitation, SQLUserRole
from corehq.apps.users.bulk_download import parse_web_users


class TestDownloadMobileWorkers(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain = 'bookshelf'
        cls.domain_obj = create_domain(cls.domain)

        cls.role = SQLUserRole.create(cls.domain, 'App Editor')
        cls.role.save()
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
            email='invited@user.com',
            domain=cls.domain_obj.name,
            invited_by='tester@test.com',
            invited_on=datetime.utcnow(),
            role=cls.qualified_role_id,
        )

    @classmethod
    def tearDownClass(cls):
        cls.user1.delete(deleted_by=None)
        cls.user2.delete(deleted_by=None)
        cls.invited_user.delete()
        cls.domain_obj.delete()
        cls.role.delete()
        super().tearDownClass()

    def test_download(self):
        (headers, rows) = parse_web_users(self.domain_obj.name)

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
        self.assertEqual('invited@user.com', spec['username'])
        self.assertEqual('invited@user.com', spec['email'])
        self.assertEqual('App Editor', spec['role'])
        self.assertEqual('Invited', spec['status'])
