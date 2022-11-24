from django.test import TestCase
from django.test.client import Client
from django.urls import reverse

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import get_simple_form, patch_validate_xform

from corehq.apps.app_manager.models import ApplicationReleaseLog
from corehq.apps.domain.models import Domain
from corehq.apps.users.models import WebUser
from corehq.util.test_utils import flag_enabled


class TestReleaseBuild(TestCase):
    @classmethod
    @patch_validate_xform()
    def setUpClass(cls):
        super().setUpClass()

        cls.client = Client()

        cls.domain_name = "fandago"
        cls.domain = Domain.get_or_create_with_name(cls.domain_name, is_active=True)

        cls.username = 'bananafana'
        cls.password = '*******'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, None, None, is_admin=True)
        cls.user.eula.signed = True
        cls.user.save()

        factory = AppFactory(cls.domain_name, name="cheeto")
        m0, f0 = factory.new_basic_module("register", "cheeto")
        f0.source = get_simple_form(xmlns=f0.unique_id)
        cls.app = factory.app
        cls.app.target_commcare_flavor = 'commcare_lts'
        cls.app.save()

        cls.app_build = cls.app.make_build()
        cls.app_build.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def test_release_build(self):
        self.client.login(username=self.username, password=self.password)
        url = reverse('release_build', args=(self.domain_name, self.app.get_id, self.app_build.get_id))
        response = self.client.post(url, {'is_released': 'true', 'ajax': 'true'})
        self.assertEqual(response.json()['is_released'], True)
        self.assertEqual(response.json()['latest_released_version'], 1)

    @flag_enabled("APPLICATION_RELEASE_LOGS")
    def test_release_build_app_release_log(self):
        self.client.login(username=self.username, password=self.password)
        url = reverse('release_build', args=(self.domain_name, self.app.get_id, self.app_build.get_id))
        response = self.client.post(url, {'is_released': 'true', 'ajax': 'true'})
        self.assertEqual(response.json()['is_released'], True)
        self.assertEqual(response.json()['latest_released_version'], 1)

        self.assertTrue(ApplicationReleaseLog.objects.filter(app_id=self.app.get_id).exists())
        logs = ApplicationReleaseLog.objects.filter(app_id=self.app.get_id).first()
        self.assertEqual(logs.action, ApplicationReleaseLog.ACTION_RELEASED)
        self.assertEqual(logs.version, self.app.version)
        self.assertEqual(logs.user_id, self.user.user_id)
