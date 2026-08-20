from unittest.mock import patch

from django.test import Client, TestCase
from django.urls import reverse

from corehq.apps.app_manager.models import Application, Module
from corehq.apps.app_manager.tests.util import get_simple_form
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.users.models import WebUser


class ValidateApiTests(TestCase):
    username = 'validate-api-user'
    password = 'correct-horse-battery-staple'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = create_domain('validate-api-domain')
        cls.user = WebUser.create(
            cls.domain.name,
            cls.username,
            cls.password,
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.user.is_superuser = True
        cls.user.save()

        cls.throttle_patcher = patch(
            'corehq.apps.api.resources.meta.HQThrottle.should_be_throttled', return_value=False
        )
        cls.throttle_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls.throttle_patcher.stop()
        cls.user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def setUp(self):
        self.app = Application.new_app(self.domain.name, 'Test App')
        module = self.app.add_module(Module.new_module('Module One', lang='en'))
        form = module.new_form('Form One', lang='en', attachment=get_simple_form(xmlns='xmlns-1'))
        self.module_id = module.unique_id
        self.form_id = form.unique_id
        self.app.save()
        self.addCleanup(self.app.delete)

        self.client = Client()
        self.client.login(username=self.username, password=self.password)

    def _app_url(self, app_id=None):
        return reverse('app_validate_api', kwargs={
            'domain': self.domain.name,
            'app_id': app_id or self.app._id,
        })

    def _form_url(self, app_id=None, module_id=None, form_id=None):
        return reverse('form_validate_api', kwargs={
            'domain': self.domain.name,
            'app_id': app_id or self.app._id,
            'module_id': module_id or self.module_id,
            'form_id': form_id or self.form_id,
        })

    def _build_url(self, app_id=None):
        return reverse('app_build_api', kwargs={
            'domain': self.domain.name,
            'app_id': app_id or self.app._id,
        })

    def test_app_valid(self):
        response = self.client.get(self._app_url())
        assert response.status_code == 200
        assert response.json() == {'valid': True, 'validation_errors': []}

    def test_app_invalid(self):
        empty_app = Application.new_app(self.domain.name, 'Empty App')
        empty_app.save()
        self.addCleanup(empty_app.delete)

        response = self.client.get(self._app_url(app_id=empty_app._id))
        assert response.status_code == 200
        body = response.json()
        assert body['valid'] is False
        assert {'type': 'no modules'} in body['validation_errors']

    def test_app_returns_404_for_missing_app(self):
        response = self.client.get(self._app_url(app_id='missing-app'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'app_not_found'

    def test_app_returns_404_for_saved_build(self):
        build = self.app.make_build()
        build.save()
        self.addCleanup(build.delete)
        response = self.client.get(self._app_url(app_id=build._id))
        assert response.status_code == 404

    def test_form_valid(self):
        response = self.client.get(self._form_url())
        assert response.status_code == 200
        assert response.json() == {'valid': True, 'validation_errors': []}

    def test_form_invalid(self):
        module = self.app.get_module_by_unique_id(self.module_id)
        blank_form = module.new_form('Blank Form', lang='en', attachment=b'')
        self.app.save()

        response = self.client.get(self._form_url(form_id=blank_form.unique_id))
        assert response.status_code == 200
        body = response.json()
        assert body['valid'] is False
        assert any(error['type'] == 'blank form' for error in body['validation_errors'])

    def test_form_returns_404_for_missing_app(self):
        response = self.client.get(self._form_url(app_id='missing-app'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'app_not_found'

    def test_form_returns_404_for_missing_module(self):
        response = self.client.get(self._form_url(module_id='missing-module'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'module_not_found'

    def test_form_returns_404_for_missing_form(self):
        response = self.client.get(self._form_url(form_id='missing-form'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'form_not_found'

    def test_build_queues_new_build(self):
        response = self.client.post(self._build_url())
        assert response.status_code == 200
        assert response.json() == {'status': 'build_queued', 'version': self.app.version}

        latest_build = self.app.get_latest_build()
        self.addCleanup(latest_build.delete)
        assert latest_build.version == self.app.version

    def test_build_returns_already_built_for_current_version(self):
        build = self.app.make_build()
        build.save()
        self.addCleanup(build.delete)

        response = self.client.post(self._build_url())
        assert response.status_code == 200
        assert response.json() == {'status': 'already_built', 'version': self.app.version}

    def test_build_returns_404_for_missing_app(self):
        response = self.client.post(self._build_url(app_id='missing-app'))
        assert response.status_code == 404
        assert response.json()['errors'][0]['error'] == 'app_not_found'

    def test_build_returns_404_for_saved_build(self):
        build = self.app.make_build()
        build.save()
        self.addCleanup(build.delete)

        response = self.client.post(self._build_url(app_id=build._id))
        assert response.status_code == 404
