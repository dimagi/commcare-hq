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
    'viewer': HqPermissions(view_document_templates=True),
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

    def test_list_and_preview_need_view(self):
        for urlname, method in [
            ('document_templates', 'get'),
            ('preview_document_variables', 'post'),
            ('preview_document', 'post'),
        ]:
            for role, expected in [('viewer', 200), ('editor', 200), ('nobody', 403)]:
                with self.subTest(urlname=urlname, role=role):
                    assert self._status(role, method, urlname) == expected

    def test_list_shows_edit_buttons_only_to_editors(self):
        for role, can_edit in [('viewer', False), ('editor', True)]:
            client = Client()
            client.login(username=f'{role}@example.com', password=PASSWORD)
            content = client.get(reverse('document_templates', args=[DOMAIN])).content.decode()
            with self.subTest(role=role):
                assert 'Welcome' in content
                for text in ['New Document Template', 'delete-template-', '/templates/new']:
                    assert (text in content) == can_edit

    def test_create_and_edit_need_edit(self):
        for urlname, args in [('new_document_template', []), ('edit_document_template', [self.template.pk])]:
            for role, expected in [('viewer', 403), ('editor', 200), ('nobody', 403)]:
                with self.subTest(urlname=urlname, role=role):
                    assert self._status(role, 'get', urlname, *args) == expected

    def test_viewer_cannot_post_a_new_template(self):
        assert self._status('viewer', 'post', 'new_document_template') == 403
        assert Template.objects.filter(domain=DOMAIN).count() == 1

    def test_delete_needs_edit(self):
        for role in ['viewer', 'nobody']:
            with self.subTest(role=role):
                assert self._status(role, 'post', 'delete_document_template', self.template.pk) == 403
                self.template.refresh_from_db()
                assert not self.template.deleted

        assert self._status('editor', 'post', 'delete_document_template', self.template.pk) == 302
        self.template.refresh_from_db()
        assert self.template.deleted
