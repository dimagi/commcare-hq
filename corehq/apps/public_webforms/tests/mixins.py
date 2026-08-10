from django.test import Client

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.public_webforms.tests.utils import DOMAIN, OTHER_DOMAIN
from corehq.apps.users.models import HqPermissions, UserRole, WebUser

PASSWORD = 'Passw0rd!'
ADMIN_USER = 'webform-admin@example.com'
NORMAL_USER = 'normal-user@example.com'
TIMEZONE = 'America/New_York'



class PublicWebformViewTestMixin:
    """Two projects, signed in as an admin who can manage public webforms.

    ``NORMAL_USER`` belongs to the same project without the permission, so the
    access gate can be exercised. Mix into a ``TestCase``.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for domain in (DOMAIN, OTHER_DOMAIN):
            domain_obj = create_domain(domain)
            # not UTC, so that anything reading it can be told apart from
            # anything defaulting to server time
            domain_obj.default_timezone = TIMEZONE
            domain_obj.save()
            # the couch doc is all that outlives a test's transaction
            cls.addClassCleanup(domain_obj.get_db().delete_doc, domain_obj.get_id)
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
