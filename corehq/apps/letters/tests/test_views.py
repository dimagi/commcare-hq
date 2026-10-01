from django.test import TestCase
from django.urls import reverse

from corehq import privileges
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.letters.models import LetterTemplate
from corehq.apps.users.models import HqPermissions, UserRole, WebUser
from corehq.util.test_utils import flag_enabled, privilege_enabled

DOMAIN = 'letters-views'


@flag_enabled('LETTER_TEMPLATES')
@privilege_enabled(privileges.OUTBOUND_SMS)
class TestLetterTemplateViews(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain_obj = create_domain(DOMAIN)
        cls.domain_obj.granted_messaging_access = True
        cls.domain_obj.save()
        cls.addClassCleanup(cls.domain_obj.delete)
        editor_role = UserRole.create(DOMAIN, 'editor', permissions=HqPermissions(edit_messaging=True))
        viewer_role = UserRole.create(DOMAIN, 'viewer', permissions=HqPermissions(edit_messaging=False))
        cls.editor = WebUser.create(DOMAIN, 'editor@x.com', 'pw', None, None, role_id=editor_role.get_id)
        cls.viewer = WebUser.create(DOMAIN, 'viewer@x.com', 'pw', None, None, role_id=viewer_role.get_id)
        cls.addClassCleanup(cls.editor.delete, DOMAIN, deleted_by=None)
        cls.addClassCleanup(cls.viewer.delete, DOMAIN, deleted_by=None)
        cls.other = LetterTemplate.objects.create(domain='other-domain', name='x', body='x')

    def _login(self, user):
        self.client.login(username=user.username, password='pw')

    def test_create(self):
        self._login(self.editor)
        resp = self.client.post(reverse('letter_template_create', args=[DOMAIN]),
                                {'name': 'Welcome', 'body': '<p>Hi {{ case_name }}</p>'})
        assert resp.status_code == 302
        assert LetterTemplate.objects.get(domain=DOMAIN, name='Welcome').body == '<p>Hi {{ case_name }}</p>'

    def test_create_rejects_bad_jinja(self):
        self._login(self.editor)
        resp = self.client.post(reverse('letter_template_create', args=[DOMAIN]),
                                {'name': 'Bad', 'body': '{% if %}'})
        assert resp.status_code == 200
        assert not LetterTemplate.objects.filter(domain=DOMAIN, name='Bad').exists()

    def test_edit_and_delete(self):
        self._login(self.editor)
        tpl = LetterTemplate.objects.create(domain=DOMAIN, name='a', body='a')
        self.client.post(reverse('letter_template_edit', args=[DOMAIN, tpl.pk]), {'name': 'b', 'body': 'b'})
        tpl.refresh_from_db()
        assert tpl.name == 'b'
        self.client.post(reverse('letter_template_delete', args=[DOMAIN, tpl.pk]))
        assert not LetterTemplate.objects.filter(pk=tpl.pk).exists()

    def test_other_domain_template_404(self):
        self._login(self.editor)
        resp = self.client.get(reverse('letter_template_edit', args=[DOMAIN, self.other.pk]))
        assert resp.status_code == 404
        resp = self.client.post(reverse('letter_template_delete', args=[DOMAIN, self.other.pk]))
        assert resp.status_code == 404
        assert LetterTemplate.objects.filter(pk=self.other.pk).exists()

    def test_no_messaging_permission_denied(self):
        self._login(self.viewer)
        resp = self.client.get(reverse('letter_template_list', args=[DOMAIN]))
        assert resp.status_code in (302, 403)

    def test_list_shows_id_and_name(self):
        self._login(self.editor)
        tpl = LetterTemplate.objects.create(domain=DOMAIN, name='Listed', body='x')
        resp = self.client.get(reverse('letter_template_list', args=[DOMAIN]))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'Listed' in content
        assert f'<td>{tpl.pk}</td>' in content

    def test_edit_page_has_preview_button(self):
        self._login(self.editor)
        resp = self.client.get(reverse('letter_template_create', args=[DOMAIN]))
        preview_url = reverse('letter_template_preview', args=[DOMAIN])
        assert f'formaction="{preview_url}"' in resp.content.decode()

    def test_preview_renders_posted_body(self):
        self._login(self.editor)
        resp = self.client.post(reverse('letter_template_preview', args=[DOMAIN]),
                                {'body': '<p>Dear {{ case_name }}!</p><script>x</script>'})
        assert resp.status_code == 200
        content = resp.content.decode()
        assert '<p>Dear !</p>' in content
        assert '<script>x' not in content

    def test_preview_shows_template_error(self):
        self._login(self.editor)
        resp = self.client.post(reverse('letter_template_preview', args=[DOMAIN]), {'body': '{% if %}'})
        assert resp.status_code == 200
        assert 'could not be rendered' in resp.content.decode()

    def test_preview_requires_messaging_permission(self):
        self._login(self.viewer)
        resp = self.client.post(reverse('letter_template_preview', args=[DOMAIN]), {'body': 'x'})
        assert resp.status_code in (302, 403)

    def test_create_page_help_text_does_not_open_style_tag(self):
        # crispy renders help text unescaped; a literal <style> would swallow the Save button
        self._login(self.editor)
        resp = self.client.get(reverse('letter_template_create', args=[DOMAIN]))
        assert resp.status_code == 200
        content = resp.content.decode()
        assert 'id="submit-id-submit"' in content
        assert '<style> blocks' not in content


@privilege_enabled(privileges.OUTBOUND_SMS)
class TestLetterTemplateToggleOff(TestCase):

    def test_list_404_without_toggle(self):
        domain_obj = create_domain('letters-no-flag')
        domain_obj.granted_messaging_access = True
        domain_obj.save()
        self.addCleanup(domain_obj.delete)
        user = WebUser.create('letters-no-flag', 'admin@x.com', 'pw', None, None, is_admin=True)
        self.addCleanup(user.delete, 'letters-no-flag', deleted_by=None)
        self.client.login(username=user.username, password='pw')
        resp = self.client.get(reverse('letter_template_list', args=['letters-no-flag']))
        assert resp.status_code == 404
