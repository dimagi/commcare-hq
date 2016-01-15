import json
import os
import re

from django.core.urlresolvers import reverse
from django.test import TestCase
from corehq.apps.app_manager.tests.util import add_build
from corehq.apps.app_manager.util import new_careplan_module
from corehq.apps.app_manager.views import AppSummaryView
from corehq.apps.builds.models import BuildSpec

from corehq import toggles
from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    APP_V1,
    APP_V2,
    Module,
    ReportModule,
    ShadowModule,
)
from .test_form_versioning import BLANK_TEMPLATE


class TestViews(TestCase):
    app = None
    build = None

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='app-manager-testviews-domain', is_active=True)
        cls.domain.save()
        cls.username = 'cornelius'
        cls.password = 'fudge'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, is_active=True)
        cls.user.is_superuser = True
        cls.user.save()
        cls.build = add_build(version='2.7.0', build_number=20655)
        cls.app = Application.new_app(cls.domain.name, "TestApp", application_version=APP_V1)
        cls.app.build_spec = BuildSpec.from_string('2.7.0/latest')
        toggles.CUSTOM_PROPERTIES.set("domain:{domain}".format(domain=cls.domain.name), True)

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.build.delete()
        if cls.app:
            cls.app.delete()
        cls.domain.delete()

    def test_download_file_bad_xform_404(self):
        '''
        This tests that the `download_file` view returns
        HTTP code 404 for XML that cannot be generated...
        in some sense it does not exist.
        '''

        module = self.app.add_module(Module.new_module("Module0", "en"))

        # These builds are checked in to the repo for use in tests
        build1 = {'version': '1.2.dev', 'build_number': 7106}
        build2 = {'version': '2.7.0', 'build_number': 20655}

        add_build(**build1)
        add_build(**build2)

        with open(os.path.join(os.path.dirname(__file__), "data", "invalid_form.xml")) as f:
            xform_str = f.read()
        self.app.new_form(module.id, name="Form0-0", attachment=xform_str, lang="en")
        self.app.save()

        response = self.client.get(reverse('app_download_file', kwargs=dict(domain=self.domain.name,
                                                                            app_id=self.app.get_id,
                                                                            path='modules-0/forms-0.xml')))
        self.assertEqual(response.status_code, 404)

    def test_edit_commcare_profile(self):
        app = Application.new_app(self.domain.name, "TestApp", application_version=APP_V2)
        app.save()
        data = {
            "custom_properties": {
                "random": "value",
                "another": "value"
            }
        }

        response = self.client.post(reverse('edit_commcare_profile', args=[self.domain.name, app._id]),
                                    json.dumps(data),
                                    content_type='application/json')

        content = json.loads(response.content)
        custom_properties = content["changed"]["custom_properties"]

        self.assertEqual(custom_properties["random"], "value")
        self.assertEqual(custom_properties["another"], "value")

        data = {
            "custom_properties": {
                "random": "changed",
            }
        }

        response = self.client.post(reverse('edit_commcare_profile', args=[self.domain.name, app._id]),
                                    json.dumps(data),
                                    content_type='application/json')

        content = json.loads(response.content)
        custom_properties = content["changed"]["custom_properties"]

        self.assertEqual(custom_properties["random"], "changed")

    def _test_status_codes(self, names, kwargs):
        for name in names:
            response = self.client.get(reverse(name, kwargs=kwargs), follow=False)
            self.assertEqual(response.status_code, 200)

    def _json_content_from_get(self, name, kwargs, data={}):
        response = self.client.get(reverse(name, kwargs=kwargs), data)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def test_basic_app(self):
        module = self.app.add_module(Module.new_module("Module0", "en"))
        form = self.app.new_form(module.id, "Form0", "en", attachment=BLANK_TEMPLATE.format(xmlns='xmlns-0.0'))
        self.app.save()

        kwargs = {
            'domain': self.domain.name,
            'app_id': self.app.id,
        }
        self._test_status_codes([
            'view_app',
            'release_manager',
            AppSummaryView.urlname,
        ], kwargs)

        self.build = self.app.make_build()
        self.build.save()
        content = self._json_content_from_get('current_app_version', {
            'domain': self.domain.name,
            'app_id': self.app.id,
        })
        self.assertEqual(content['currentVersion'], 2)

        content = self._json_content_from_get('paginate_releases', {
            'domain': self.domain.name,
            'app_id': self.app.id,
        }, {'limit': 5})
        self.assertEqual(len(content), 1)
        content = content[0]
        self.assertEqual(content['copy_of'], self.app.id)

        kwargs['module_id'] = module.id
        self._test_status_codes(['view_module'], kwargs)

        kwargs['form_id'] = form.id
        self._test_status_codes(['view_form', 'form_source'], kwargs)

    def test_user_registration(self):
        self.app.show_user_registration = True
        self.app.save()
        self._test_status_codes([
            'view_user_registration',
            'user_registration_source',
        ], {
            'domain': self.domain.name,
            'app_id': self.app.id,
        })

    def test_advanced_module(self):
        module = self.app.add_module(AdvancedModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.domain.name,
            'app_id': self.app.id,
            'module_id': module.id,
        })

    def test_report_module(self):
        module = self.app.add_module(ReportModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.domain.name,
            'app_id': self.app.id,
            'module_id': module.id,
        })

    def test_shadow_module(self):
        module = self.app.add_module(ShadowModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.domain.name,
            'app_id': self.app.id,
            'module_id': module.id,
        })

    def test_careplan_module(self):
        target_module = self.app.add_module(Module.new_module("Module0", "en"))
        target_module.case_type = 'person'

        module = new_careplan_module(self.app, 'Module1', 'en', target_module)

        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.domain.name,
            'app_id': self.app.id,
            'module_id': module.id,
        })


class TestTemplateAppViews(TestCase):

    @classmethod
    def setUpClass(cls):
        cls.domain = Domain(name='template-app-testviews-domain', is_active=True)
        cls.domain.save()
        cls.username = 'cornelius'
        cls.password = 'fudge'
        cls.user = WebUser.create(cls.domain.name, cls.username, cls.password, is_active=True)
        cls.user.is_superuser = True
        cls.user.save()

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.domain.delete()

    def _check_response(self, response):
        self.assertEqual(response.status_code, 302)
        redirect_location = response['Location']
        [app_id] = re.compile(r'[a-fA-F0-9]{32}').findall(redirect_location)
        expected = '{}/modules-0/forms-0/'.format(app_id)
        self.assertTrue(redirect_location.endswith(expected))
        self.addCleanup(lambda: Application.get_db().delete_doc(app_id))

    def test_app_from_template(self):
        response = self.client.get(reverse('app_from_template', kwargs={
            'domain': self.domain.name,
            'slug': 'case_management'
        }), follow=False)

        self._check_response(response)

    def test_default_new_app(self):
        response = self.client.get(reverse('default_new_app', kwargs={
            'domain': self.domain.name,
        }), follow=False)

        self._check_response(response)
