import datetime

from django.test import Client, TestCase
from django.utils import timezone

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.public_webforms.models import PublicWebform
from corehq.apps.users.models import HqPermissions, UserRole, WebUser

DOMAIN = 'public-forms-domain'
OTHER_DOMAIN = 'public-forms-other-domain'
PASSWORD = 'Passw0rd!'
ADMIN_USER = 'webform-admin@example.com'
NORMAL_USER = 'normal-user@example.com'


def create_webform(**kwargs):
    return PublicWebform.objects.create(**{
        'domain': DOMAIN,
        'label': 'Antenatal visit',
        'app_id': 'app',
        'app_build_id': 'build',
        'form_unique_id': 'form',
        'endpoint_id': 'endpoint',
        'session_type': 'survey',
        'allow_sms': False,
        'allow_email': True,
        'expires_at': timezone.now() + datetime.timedelta(days=30),
        **kwargs,
    })


class PublicWebformViewTestCase(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for domain in (DOMAIN, OTHER_DOMAIN):
            domain_obj = create_domain(domain)
            cls.addClassCleanup(domain_obj.delete)
        cls.make_user(ADMIN_USER, HqPermissions(edit_public_webforms=True))
        cls.make_user(NORMAL_USER, HqPermissions())

    @classmethod
    def make_user(cls, username, permissions):
        role = UserRole.create(DOMAIN, username, permissions=permissions)
        user = WebUser.create(
            domain=DOMAIN,
            username=username,
            password=PASSWORD,
            role_id=role.get_id,
            created_by=None,
            created_via=None,
        )
        cls.addClassCleanup(user.delete, DOMAIN, deleted_by=None)
        return user

    def setUp(self):
        super().setUp()
        self.client = Client()
        self.sign_in(ADMIN_USER)

    def sign_in(self, username):
        self.client.login(username=username, password=PASSWORD)
