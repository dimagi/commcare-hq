import base64
import json
import re
from contextlib import contextmanager
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from corehq.apps.app_manager.exceptions import XFormValidationError
from corehq.apps.app_manager.models import (
    AdvancedModule,
    Application,
    FormDatum,
    FormLink,
    Module,
    ReportModule,
    ShadowModule,
)
from corehq.apps.app_manager.tests.util import add_build, get_simple_form
from corehq.apps.app_manager.views import (
    AppCaseSummaryView,
    AppFormSummaryView,
)
from corehq.apps.app_manager.views.forms import (
    _get_form_links,
    _get_linkable_forms_context,
    get_apps_modules,
)
from corehq.apps.builds.models import BuildSpec
from corehq.apps.domain.models import Domain
from corehq.apps.es.apps import app_adapter
from corehq.apps.es.tests.utils import es_test
from corehq.apps.linked_domain.applications import create_linked_app
from corehq.apps.users.models import HQApiKey, WebUser
from corehq.util.test_utils import flag_enabled, timelimit

from .app_factory import AppFactory
from .test_form_versioning import INVALID_TEMPLATE

User = get_user_model()


@flag_enabled('CUSTOM_PROPERTIES')
@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
@es_test(requires=[app_adapter], setup_class=True)
class TestViews(TestCase):
    app = None
    build = None

    @classmethod
    def setUpClass(cls):
        super(TestViews, cls).setUpClass()
        cls.project = Domain.get_or_create_with_name('app-manager-testviews-domain', is_active=True)
        cls.username = 'cornelius'
        cls.password = 'fudge'
        cls.user = WebUser.create(cls.project.name, cls.username, cls.password, None, None, is_active=True)
        cls.user.is_superuser = True
        cls.user.save()
        cls.build = add_build(version='2.7.0', build_number=20655)

    def setUp(self):
        self.app = Application.new_app(self.project.name, "TestApp")
        self.app.build_spec = BuildSpec.from_string('2.7.0/latest')
        self.client.login(username=self.username, password=self.password)

    def tearDown(self):
        if self.app._id:
            self.app.delete()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.project.name, deleted_by=None)
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
        app_adapter.index(app, refresh=True)

    @timelimit(90)
    @patch('corehq.apps.app_manager.views.formdesigner.form_has_submissions', return_value=True)
    def test_basic_app(self, mock1, mock2):
        module = self.app.add_module(Module.new_module("Module0", "en"))
        form = self.app.new_form(module.id, "Form0", "en", attachment=get_simple_form(xmlns='xmlns-0.0'))
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

        mock2.side_effect = XFormValidationError('')
        bad_form = self.app.new_form(module.id, "Form1", "en",
                                     attachment=INVALID_TEMPLATE.format(xmlns='xmlns-0.0'))
        kwargs['form_unique_id'] = bad_form.unique_id
        self.app.save()
        self._test_status_codes(['view_form', 'form_source'], kwargs)

        bad_form = self.app.new_form(module.id, "Form1", "en",
                                     attachment="this is not xml")
        kwargs['form_unique_id'] = bad_form.unique_id
        self.app.save()
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

    def test_form_linking_context(self, _):
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m2f0 = factory.new_basic_module('m1', 'frog')
        m1.case_details.short.multi_select = True
        # shadow module
        factory.new_shadow_module('m2', m0, with_form=False)
        # module with different case type
        factory.new_basic_module('m3', 'rabbit')

        linkables = _get_linkable_forms_context(m0, factory.app.langs)
        self.assertEqual(linkables, [
            {
                'allow_manual_linking': False,
                'auto_link': True,
                'name': 'm0 module',
                'unique_id': 'm0_module'
            },
            {
                'allow_manual_linking': True,
                'auto_link': True,
                'name': 'm0 module > m0 form 0',
                'unique_id': 'm0_module.m0_form_0'
            },
            {
                'allow_manual_linking': False,
                'auto_link': True,
                'name': 'm1 module',
                'unique_id': 'm1_module'
            },
            {
                'allow_manual_linking': True,
                'auto_link': True,
                'name': 'm1 module > m1 form 0',
                'unique_id': 'm1_module.m1_form_0'
            },
            {
                'allow_manual_linking': False,
                'auto_link': True,
                'name': 'm2 module',
                'unique_id': 'm2_module'
            },
            {
                'allow_manual_linking': True,
                'auto_link': True,
                'name': 'm2 module > m0 form 0',
                'unique_id': 'm2_module.m0_form_0'
            },
            {
                'allow_manual_linking': False,
                'auto_link': True,
                'name': 'm3 module',
                'unique_id': 'm3_module'
            },
            {
                'allow_manual_linking': True,
                'auto_link': False,  # can't autolink to a form with a different case type
                'name': 'm3 module > m3 form 0',
                'unique_id': 'm3_module.m3_form_0'
            }
        ])

    def test_form_linking_context_multi_select(self, _):
        factory = AppFactory(build_version='2.9.0')
        factory.new_basic_module('m0', 'frog')

        m1, m2f0 = factory.new_basic_module('m1', 'frog')
        m1.case_details.short.multi_select = True

        linkables = _get_linkable_forms_context(m1, factory.app.langs)

        # no auto linking allowed
        self.assertEqual(linkables, [
            {
                'allow_manual_linking': False,
                'auto_link': True,
                'name': 'm0 module',
                'unique_id': 'm0_module'
            },
            {
                'allow_manual_linking': True,
                'auto_link': False,
                'name': 'm0 module > m0 form 0',
                'unique_id': 'm0_module.m0_form_0'
            },
            {
                'allow_manual_linking': False,
                'auto_link': True,
                'name': 'm1 module',
                'unique_id': 'm1_module'
            },
            {
                'allow_manual_linking': True,
                'auto_link': False,
                'name': 'm1 module > m1 form 0',
                'unique_id': 'm1_module.m1_form_0'
            },
        ])

    def test_form_links_context(self, _):
        self.maxDiff = None
        factory = AppFactory(build_version='2.9.0')
        m0, m0f0 = factory.new_basic_module('m0', 'frog')
        m1, m1f0 = factory.new_basic_module('m1', 'frog')
        m0f0.form_links = [
            FormLink(xpath="true()", form_id=m1f0.unique_id, form_module_id=m1.unique_id, datums=[
                FormDatum(name="case_id", xpath="instance('commcaresession')/session/data/case_id")
            ]),
            FormLink(xpath="true()", form_id=m1f0.unique_id),
            FormLink(xpath="true()", form_id="DELETED_ID"),  # this won't appear in the context
            FormLink(module_unique_id=m1.unique_id),
        ]
        links = _get_form_links(factory.app, m0f0)
        self.assertEqual(links, [
            {
                'datums': [
                    {
                        'doc_type': 'FormDatum',
                        'name': 'case_id',
                        'xpath': "instance('commcaresession')/session/data/case_id"
                    }
                ],
                'doc_type': 'FormLink',
                'form_id': 'm1_form_0',
                'form_module_id': 'm1_module',
                'module_unique_id': None,
                'uniqueId': 'm1_module.m1_form_0',
                'xpath': 'true()'
            },
            # legacy data still produced the correct uniqueId
            {
                'datums': [],
                'doc_type': 'FormLink',
                'form_id': 'm1_form_0',
                'form_module_id': None,
                'module_unique_id': None,
                'uniqueId': 'm1_module.m1_form_0',
                'xpath': 'true()'
            },
            {
                'datums': [],
                'doc_type': 'FormLink',
                'form_id': None,
                'form_module_id': None,
                'module_unique_id': 'm1_module',
                'uniqueId': 'm1_module',
                'xpath': None
            }
        ])


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


class TestDownloadCaseSummaryViewByAPIKey(TestCase):
    """Test that the DownloadCaseSummaryView can be accessed with an API key."""

    @classmethod
    def setUpClass(cls):
        # Set up a domain and an app.
        super().setUpClass()
        cls.domain = Domain.get_by_name("test-domain")
        if not cls.domain:
            cls.domain = Domain(name="test-domain", is_active=True)
        cls.domain.save()
        cls.app = Application.new_app("test-domain", "TestApp")
        cls.app.save()

        # Set up the cls.web_user: set password and give access to the cls.domain.
        old_web_user = WebUser.get_by_username("test_user")
        if old_web_user:
            old_web_user.delete(cls.domain.name, deleted_by=None)
        cls.web_user = WebUser.create(
            cls.domain.name, "test_user", "my_password", None, None, is_active=True
        )

        # Generate an API key for the cls.web_user.
        cls.web_user_api_key = HQApiKey.objects.get_or_create(
            user=cls.web_user.get_django_user()
        )[0]
        cls.web_user_api_key.key = cls.web_user_api_key.generate_key()
        cls.web_user_api_key.save()

        # The URL that tests in this class will use.
        cls.url = reverse(
            "download_case_summary",
            kwargs={"domain": cls.domain.name, "app_id": cls.app.get_id},
        )

    @classmethod
    def tearDownClass(cls):
        cls.app.delete()
        cls.web_user_api_key.delete()
        cls.web_user.delete(cls.domain.name, deleted_by=None)
        cls.domain.delete()
        super().tearDownClass()

    def _encode_basic_credentials(self, username, password):
        """Base64-encode a username and password."""
        return base64.b64encode(
            "{}:{}".format(username, password).encode("utf-8")
        ).decode("utf-8")

    def test_correct_api_key(self):
        """Sending a correct API key returns a response with the case summary file."""
        response = self.client.get(
            self.url,
            HTTP_AUTHORIZATION=f"ApiKey {self.web_user.username}:{self.web_user_api_key.key}",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], "application/vnd.ms-excel")

    def test_incorrect_api_key(self):
        """Sending an incorrect (or missing) API key returns a 401 response."""
        with self.subTest("Missing API key"):
            response = self.client.get(
                self.url, HTTP_AUTHORIZATION=f"ApiKey {self.web_user.username}:"
            )
            self.assertEqual(response.status_code, 401)

        with self.subTest("Missing username"):
            response = self.client.get(
                self.url, HTTP_AUTHORIZATION=f"ApiKey :{self.web_user_api_key.key}"
            )
            self.assertEqual(response.status_code, 401)

        with self.subTest("Missing header"):
            response = self.client.get(self.url)
            self.assertEqual(response.status_code, 401)

        with self.subTest("Incorrect API key"):
            response = self.client.get(
                self.url,
                HTTP_AUTHORIZATION=f"ApiKey {self.web_user.username}:Incorrectkey",
            )
            self.assertEqual(response.status_code, 401)

    def test_already_authenticated_does_not_need_api_key(self):
        """If a user is already authenticated, then the user does not need to send an API key."""
        # Authenticate the user.
        self.client.force_login(self.web_user.get_django_user())

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers['content-type'], "application/vnd.ms-excel")

    def test_unsupported_request_methods(self):
        """Test sending requests by unsupported HTTP methods to the view."""
        unsupported_methods = ["POST", "PUT", "PATCH", "DELETE"]
        for method_name in unsupported_methods:
            with self.subTest(method_name=method_name):
                request_method = getattr(self.client, method_name.lower())
                response = request_method(self.url)
                self.assertEqual(response.status_code, 405)

    def test_correct_credentials(self):
        """Sending valid or invalid username & password does not succeed."""
        with self.subTest("Valid credentials"):
            valid_credentials = self._encode_basic_credentials(
                self.web_user.username, "my_password"
            )
            response = self.client.get(
                self.url, HTTP_AUTHORIZATION=f"Basic {valid_credentials}"
            )
            self.assertEqual(response.status_code, 401)

        with self.subTest("Invalid credentials"):
            invalid_credentials = self._encode_basic_credentials(
                self.web_user.username, "not_the_correct_password"
            )
            response = self.client.get(
                self.url, HTTP_AUTHORIZATION=f"Basic {invalid_credentials}"
            )
            self.assertEqual(response.status_code, 401)
