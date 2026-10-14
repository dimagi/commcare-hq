from django.test import TestCase
from django.urls import reverse

from corehq.apps.hqadmin.models import PlatformDeactivationLog
from corehq.apps.users.models import WebUser


class TestPlatformDeactivationLogAdmin(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.superuser = WebUser.create(None, 'super@dimagi.com', 'password', None, None, is_superuser=True)
        cls.addClassCleanup(cls.superuser.delete, None, None)
        django_user = cls.superuser.get_django_user()
        django_user.is_staff = True
        django_user.save()
        cls.log = PlatformDeactivationLog.objects.create(
            performed_by='admin@dimagi.com', target_email='jane@dimagi.com', platform='sentry',
            account_label='Jane Doe <jane@dimagi.com>', succeeded=True, detail='Removed Jane Doe',
        )

    def setUp(self):
        assert self.client.login(username=self.superuser.username, password='password')

    def test_changelist_lists_entries(self):
        response = self.client.get(reverse('admin:hqadmin_platformdeactivationlog_changelist'))
        assert response.status_code == 200
        assert b'jane@dimagi.com' in response.content

    def test_detail_is_view_only(self):
        response = self.client.get(reverse('admin:hqadmin_platformdeactivationlog_change', args=[self.log.pk]))
        assert response.status_code == 200
        assert b'name="_save"' not in response.content

    def test_add_is_forbidden(self):
        response = self.client.get(reverse('admin:hqadmin_platformdeactivationlog_add'))
        assert response.status_code == 403

    def test_delete_is_forbidden(self):
        response = self.client.post(
            reverse('admin:hqadmin_platformdeactivationlog_delete', args=[self.log.pk]), {'post': 'yes'})
        assert response.status_code == 403
        assert PlatformDeactivationLog.objects.filter(pk=self.log.pk).exists()

    def test_change_is_forbidden(self):
        response = self.client.post(
            reverse('admin:hqadmin_platformdeactivationlog_change', args=[self.log.pk]),
            {'target_email': 'someone-else@dimagi.com'})
        assert response.status_code == 403
        self.log.refresh_from_db()
        assert self.log.target_email == 'jane@dimagi.com'
