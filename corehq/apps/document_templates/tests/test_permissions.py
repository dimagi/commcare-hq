from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.document_templates.models import Template
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import HqPermissions, WebUser
from corehq.apps.users.models_role import UserRole
from corehq.util.test_utils import flag_enabled

DOMAIN = 'document-templates-permissions-test'
PASSWORD = 'Passw0rd!'
ROLES = {
    'editor': HqPermissions(edit_document_templates=True),
    'nobody': HqPermissions(),
}


@flag_enabled('DOCUMENT_TEMPLATES')
class TestDocumentTemplatePermissions(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.addClassCleanup(cls.domain_obj.delete)
        for name, permissions in ROLES.items():
            permissions.normalize()  # as the role editor does when saving
            user = WebUser.create(DOMAIN, f'{name}@example.com', PASSWORD, None, None)
            role = UserRole.create(domain=cls.domain_obj, name=name, permissions=permissions)
            user.set_role(DOMAIN, role.get_qualified_id())
            user.save()
            cls.addClassCleanup(user.delete, DOMAIN, deleted_by=None)

    def setUp(self):
        self.template = Template.objects.create(domain=DOMAIN, name='Welcome', slug='welcome', areas={})

    def _status(self, role, method, urlname, *args):
        client = Client()
        client.login(username=f'{role}@example.com', password=PASSWORD)
        return getattr(client, method)(reverse(urlname, args=[DOMAIN, *args])).status_code

    def test_views_need_edit(self):
        for urlname, method, args in [
            ('document_templates', 'get', []),
            ('preview_document_variables', 'post', []),
            ('preview_document', 'post', []),
            ('new_document_template', 'get', []),
            ('new_document_template', 'post', []),
            ('edit_document_template', 'get', [self.template.pk]),
            ('upload_document_template_image', 'post', ['header']),
        ]:
            for role, expected in [('editor', 200), ('nobody', 403)]:
                with self.subTest(urlname=urlname, method=method, role=role):
                    assert self._status(role, method, urlname, *args) == expected

    def test_delete_needs_edit(self):
        assert self._status('nobody', 'post', 'delete_document_template', self.template.pk) == 403
        self.template.refresh_from_db()
        assert not self.template.deleted

        assert self._status('editor', 'post', 'delete_document_template', self.template.pk) == 302
        self.template.refresh_from_db()
        assert self.template.deleted
