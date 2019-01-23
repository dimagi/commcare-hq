from __future__ import absolute_import
from __future__ import unicode_literals
import json
import re
from contextlib import contextmanager

from django.urls import reverse
from django.test import TestCase
from mock import patch

from corehq.elastic import get_es_new, send_to_elasticsearch
from corehq.apps.app_manager.exceptions import XFormValidationError
from corehq.apps.app_manager.tests.util import add_build
from corehq.apps.app_manager.views import AppCaseSummaryView, AppFormSummaryView
from corehq.apps.app_manager.views.forms import get_apps_modules
from corehq.apps.builds.models import BuildSpec
from pillowtop.es_utils import initialize_index_and_mapping
from corehq.pillows.mappings.app_mapping import APP_INDEX_INFO

from corehq import toggles
from corehq.apps.linked_domain.applications import create_linked_app
from corehq.apps.users.models import WebUser
from corehq.apps.domain.models import Domain
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    Module,
    ReportModule,
    ShadowModule,
)
from .test_form_versioning import BLANK_TEMPLATE


@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
class TestViews(TestCase):
    app = None
    build = None

    @classmethod
    def setUpClass(cls):
        super(TestViews, cls).setUpClass()
        cls.project = Domain(name='app-manager-testviews-domain', is_active=True)
        cls.project.save()
        cls.username = 'cornelius'
        cls.password = 'fudge'
        cls.user = WebUser.create(cls.project.name, cls.username, cls.password, is_active=True)
        cls.user.is_superuser = True
        cls.user.save()
        cls.build = add_build(version='2.7.0', build_number=20655)
        cls.es = get_es_new()
        initialize_index_and_mapping(cls.es, APP_INDEX_INFO)

        toggles.CUSTOM_PROPERTIES.set("domain:{domain}".format(domain=cls.project.name), True)

    def setUp(self):
        self.app = Application.new_app(self.project.name, "TestApp")
        self.app.build_spec = BuildSpec.from_string('2.7.0/latest')
        self.client.login(username=self.username, password=self.password)

    def tearDown(self):
        if self.app._id:
            self.app.delete()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.build.delete()
        cls.project.delete()
        super(TestViews, cls).tearDownClass()

    def test_download_file_bad_xform_404(self, mock):
        '''
        This tests that the `download_file` view returns
        HTTP code 404 for XML that cannot be generated...
        in some sense it does not exist.
        '''

        module = self.app.add_module(Module.new_module("Module0", "en"))

        # These builds are checked in to the repo for use in tests
        build1 = {'version': '1.2.0', 'build_number': 7106}
        build2 = {'version': '2.7.0', 'build_number': 20655}

        add_build(**build1)
        add_build(**build2)

        self.app.new_form(module.id, name="Form0-0", lang="en")
        self.app.save()

        mock.side_effect = XFormValidationError('')
        response = self.client.get(reverse('app_download_file', kwargs=dict(domain=self.project.name,
                                                                            app_id=self.app.get_id,
                                                                            path='modules-0/forms-0.xml')))
        self.assertEqual(response.status_code, 404)

    def test_edit_commcare_profile(self, mock):
        app2 = Application.new_app(self.project.name, "TestApp2")
        app2.save()
        self.addCleanup(lambda: Application.get_db().delete_doc(app2.id))
        data = {
            "custom_properties": {
                "random": "value",
                "another": "value"
            }
        }

        response = self.client.post(reverse('edit_commcare_profile', args=[self.project.name, app2._id]),
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

        response = self.client.post(reverse('edit_commcare_profile', args=[self.project.name, app2._id]),
                                    json.dumps(data),
                                    content_type='application/json')

        content = json.loads(response.content)
        custom_properties = content["changed"]["custom_properties"]

        self.assertEqual(custom_properties["random"], "changed")

    def _test_status_codes(self, names, kwargs, follow=False):
        for name in names:
            response = self.client.get(reverse(name, kwargs=kwargs), follow=follow)
            self.assertEqual(response.status_code, 200)

    def _json_content_from_get(self, name, kwargs, data={}):
        response = self.client.get(reverse(name, kwargs=kwargs), data)
        self.assertEqual(response.status_code, 200)
        return json.loads(response.content)

    def _send_to_es(self, app):
        send_to_elasticsearch('apps', app.to_json())
        self.es.indices.refresh(APP_INDEX_INFO.index)

    @patch('corehq.apps.app_manager.views.formdesigner.form_has_submissions', return_value=True)
    def test_basic_app(self, mock1, mock2):
        module = self.app.add_module(Module.new_module("Module0", "en"))
        form = self.app.new_form(module.id, "Form0", "en", attachment=BLANK_TEMPLATE.format(xmlns='xmlns-0.0'))
        self.app.save()
        self._send_to_es(self.app)

        kwargs = {
            'domain': self.project.name,
            'app_id': self.app.id,
        }
        self._test_status_codes([
            'view_app',
            'release_manager',
            AppCaseSummaryView.urlname,
            AppFormSummaryView.urlname,
        ], kwargs)

        build = self.app.make_build()
        build.save()
        self._send_to_es(build)

        content = self._json_content_from_get('current_app_version', {
            'domain': self.project.name,
            'app_id': self.app.id,
        })
        self.assertEqual(content['currentVersion'], 1)
        self.app.save()
        self._send_to_es(self.app)

        content = self._json_content_from_get('current_app_version', {
            'domain': self.project.name,
            'app_id': self.app.id,
        })
        self.assertEqual(content['currentVersion'], 2)

        content = self._json_content_from_get('paginate_releases', {
            'domain': self.project.name,
            'app_id': self.app.id,
        }, {'limit': 5})
        self.assertEqual(len(content['apps']), 1)
        content = content['apps'][0]
        self.assertEqual(content['copy_of'], self.app.id)

        kwargs['module_unique_id'] = module.unique_id
        self._test_status_codes(['view_module'], kwargs)

        del kwargs['module_unique_id']
        kwargs['form_unique_id'] = form.unique_id
        self._test_status_codes(['view_form', 'form_source'], kwargs)

    def test_advanced_module(self, mock):
        module = self.app.add_module(AdvancedModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.project.name,
            'app_id': self.app.id,
            'module_unique_id': module.unique_id,
        })

    def test_report_module(self, mockh):
        module = self.app.add_module(ReportModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.project.name,
            'app_id': self.app.id,
            'module_unique_id': module.unique_id,
        })

    def test_shadow_module(self, mockh):
        module = self.app.add_module(ShadowModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.project.name,
            'app_id': self.app.id,
            'module_unique_id': module.unique_id,
        })

    def test_dashboard(self, mock):
        # This redirects to the dashboard
        self._test_status_codes(['default_app'], {
            'domain': self.project.name,
        }, True)

    def test_default_new_app(self, mock):
        response = self.client.get(reverse('default_new_app', kwargs={
            'domain': self.project.name,
        }), follow=False)

        self.assertEqual(response.status_code, 302)
        redirect_location = response['Location']
        [app_id] = re.compile(r'[a-fA-F0-9]{32}').findall(redirect_location)
        expected = '/apps/view/{}/'.format(app_id)
        self.assertTrue(redirect_location.endswith(expected))
        self.addCleanup(lambda: Application.get_db().delete_doc(app_id))

    def test_get_apps_modules(self, mock):
        with apps_modules_setup(self):
            apps_modules = get_apps_modules(self.project.name)

            names = sorted([a['name'] for a in apps_modules])
            self.assertEqual(
                names, ['OtherApp', 'TestApp'],
                'get_apps_modules should only return normal Applications'
            )
            self.assertTrue(
                all(len(app['modules']) == 1 for app in apps_modules),
                'Each app should only have one module'
            )
            self.assertEqual(
                apps_modules[0]['modules'][0]['name'], 'Module0',
                'Module name should be translated'
            )

    def test_get_apps_modules_doc_types(self, mock):
        with apps_modules_setup(self):
            apps_modules = get_apps_modules(
                self.project.name, app_doc_types=('Application', 'LinkedApplication')
            )
            names = sorted([a['name'] for a in apps_modules])
            self.assertEqual(names, ['LinkedApp', 'OtherApp', 'TestApp'])


@contextmanager
def apps_modules_setup(test_case):
    """
    Additional setUp and tearDown for get_apps_modules tests
    """
    test_case.app.add_module(Module.new_module("Module0", "en"))
    test_case.app.save()

    test_case.other_app = Application.new_app(test_case.project.name, "OtherApp")
    test_case.other_app.add_module(Module.new_module("Module0", "en"))
    test_case.other_app.save()

    test_case.deleted_app = Application.new_app(test_case.project.name, "DeletedApp")
    test_case.deleted_app.add_module(Module.new_module("Module0", "en"))
    test_case.deleted_app.save()
    test_case.deleted_app.delete_app()
    test_case.deleted_app.save()  # delete_app() changes doc_type. This save() saves that.

    test_case.linked_app = create_linked_app(test_case.project.name, test_case.app.id,
                                             test_case.project.name, 'LinkedApp')
    try:
        yield
    finally:
        Application.get_db().delete_doc(test_case.linked_app.id)
        Application.get_db().delete_doc(test_case.deleted_app.id)
        Application.get_db().delete_doc(test_case.other_app.id)
