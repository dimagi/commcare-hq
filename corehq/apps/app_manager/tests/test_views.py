import base64
import doctest
import json
import re
from contextlib import contextmanager
from unittest import mock
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


class ViewsBase(TestCase):
    domain = 'test-views-base'
    username = 'dolores.umbridge'
    password = 'bumblesn0re'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.domain_obj = Domain.get_or_create_with_name(
            cls.domain,
            is_active=True,
        )
        cls.build = add_build(version='2.7.0', build_number=20655)

        cls.user = WebUser.create(
            cls.domain,
            cls.username,
            cls.password,
            created_by=None,
            created_via=None,
            is_active=True,
        )
        cls.user.is_superuser = True
        cls.user.save()

    @classmethod
    def tearDownClass(cls):
        cls.user.delete(cls.domain, deleted_by=None)
        cls.build.delete()
        cls.domain_obj.delete()
        super().tearDownClass()


@flag_enabled('CUSTOM_PROPERTIES')
@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
@es_test(requires=[app_adapter], setup_class=True)
class TestViews(ViewsBase):
    domain = 'app-manager-testviews-domain'
    username = 'cornelius'
    password = 'fudge'

    def setUp(self):
        self.app = Application.new_app(self.domain, "TestApp")
        self.app.build_spec = BuildSpec.from_string('2.7.0/latest')
        self.client.login(username=self.username, password=self.password)

    def tearDown(self):
        if self.app._id:
            self.app.delete()

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
        response = self.client.get(reverse('app_download_file', kwargs=dict(domain=self.domain,
                                                                            app_id=self.app.get_id,
                                                                            path='modules-0/forms-0.xml')))
        self.assertEqual(response.status_code, 404)

    def test_edit_commcare_profile(self, mock):
        app2 = Application.new_app(self.domain, "TestApp2")
        app2.save()
        self.addCleanup(lambda: Application.get_db().delete_doc(app2.id))
        data = {
            "custom_properties": {
                "random": "value",
                "another": "value"
            }
        }

        response = self.client.post(reverse('edit_commcare_profile', args=[self.domain, app2._id]),
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

        response = self.client.post(reverse('edit_commcare_profile', args=[self.domain, app2._id]),
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
            'domain': self.domain,
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
            'domain': self.domain,
            'app_id': self.app.id,
        })
        self.assertEqual(content['currentVersion'], 1)
        self.app.save()
        self._send_to_es(self.app)

        content = self._json_content_from_get('current_app_version', {
            'domain': self.domain,
            'app_id': self.app.id,
        })
        self.assertEqual(content['currentVersion'], 2)

        content = self._json_content_from_get('paginate_releases', {
            'domain': self.domain,
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
            'domain': self.domain,
            'app_id': self.app.id,
            'module_unique_id': module.unique_id,
        })

    def test_report_module(self, mockh):
        module = self.app.add_module(ReportModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.domain,
            'app_id': self.app.id,
            'module_unique_id': module.unique_id,
        })

    def test_shadow_module(self, mockh):
        module = self.app.add_module(ShadowModule.new_module("Module0", "en"))
        self.app.save()
        self._test_status_codes(['view_module'], {
            'domain': self.domain,
            'app_id': self.app.id,
            'module_unique_id': module.unique_id,
        })

    def test_default_new_app(self, mock):
        response = self.client.get(reverse('default_new_app', kwargs={
            'domain': self.domain,
        }), follow=False)

        self.assertEqual(response.status_code, 302)
        redirect_location = response['Location']
        [app_id] = re.compile(r'[a-fA-F0-9]{32}').findall(redirect_location)
        expected = '/apps/view/{}/'.format(app_id)
        self.assertTrue(redirect_location.endswith(expected))
        self.addCleanup(lambda: Application.get_db().delete_doc(app_id))

    def test_get_apps_modules(self, mock):
        with apps_modules_setup(self):
            apps_modules = get_apps_modules(self.domain)

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
                self.domain, app_doc_types=('Application', 'LinkedApplication')
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

    def test_copy_regular_app(self, _):
        other_domain = Domain.get_or_create_with_name('other-domain', is_active=True)
        self.addCleanup(other_domain.delete)

        module = self.app.add_module(Module.new_module("Module0", "en"))
        self.app.new_form(module.id, "Form0", "en", attachment=get_simple_form(xmlns='xmlns-0.0'))
        self.app.save()

        copy_data = {
            'app': self.app.id,
            'domain': other_domain.name,
            'name': 'Copy App',
            'linked': False,
        }
        response = self.client.post(reverse('copy_app', args=[self.domain]), copy_data)
        self.assertEqual(response.status_code, 302)

        copied_app = other_domain.full_applications()[0]
        self.assertEqual(copied_app.name, 'Copy App')
        self.assertEqual(copied_app.doc_type, 'Application')

        copied_module = copied_app.modules[0]
        copied_form = list(copied_module.get_forms())[0]
        self.assertEqual(copied_module.name['en'], "Module0")
        self.assertEqual(copied_form.name['en'], "Form0")

        copied_app.delete()

    def test_copy_linked_app_to_different_domain(self, _):
        other_domain = Domain.get_or_create_with_name('other-domain', is_active=True)
        self.addCleanup(other_domain.delete)

        module = self.app.add_module(Module.new_module("Module0", "en"))
        self.app.new_form(module.id, "Form0", "en", attachment=get_simple_form(xmlns='xmlns-0.0'))
        self.app.save()
        build = self.app.make_build()
        build.is_released = True
        build.save()

        copy_data = {
            'app': self.app.id,
            'domain': other_domain.name,
            'name': 'Linked App',
            'linked': True,
            'build_id': build.id,
        }
        with patch('corehq.apps.app_manager.forms.can_domain_access_linked_domains', return_value=True):
            response = self.client.post(reverse('copy_app', args=[self.domain]), copy_data)
        self.assertEqual(response.status_code, 302)

        linked_app = other_domain.full_applications()[0]
        self.assertEqual(linked_app.name, 'Linked App')
        self.assertEqual(linked_app.doc_type, 'LinkedApplication')

        linked_module = linked_app.modules[0]
        linked_form = list(linked_module.get_forms())[0]
        self.assertEqual(linked_module.name['en'], "Module0")
        self.assertEqual(linked_form.name['en'], "Form0")

        linked_app.delete()

    def test_cannot_copy_linked_app_to_same_domain(self, _):
        module = self.app.add_module(Module.new_module("Module0", "en"))
        self.app.new_form(module.id, "Form0", "en", attachment=get_simple_form(xmlns='xmlns-0.0'))
        self.app.save()
        build = self.app.make_build()
        build.is_released = True
        build.save()

        copy_data = {
            'app': self.app.id,
            'domain': self.domain,
            'name': 'Same Domain Link',
            'linked': True,
            'build_id': build.id,
        }
        with patch('corehq.apps.app_manager.forms.can_domain_access_linked_domains', return_value=True):
            response = self.client.post(reverse('copy_app', args=[self.domain]), copy_data)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            ['Creating linked app failed. '
             'You cannot create a linked app in the same project space as the upstream app.'],
            [m.message for m in response.wsgi_request._messages]
        )

    def test_copy_regular_app_toggles(self, _):
        other_domain = Domain.get_or_create_with_name('other-domain', is_active=True)
        self.addCleanup(other_domain.delete)

        module = self.app.add_module(Module.new_module("Module0", "en"))
        self.app.new_form(module.id, "Form0", "en", attachment=get_simple_form(xmlns='xmlns-0.0'))
        self.app.save()

        from corehq.toggles import NAMESPACE_DOMAIN, StaticToggle, TAG_INTERNAL
        from corehq.toggles.shortcuts import set_toggle

        TEST_TOGGLE = StaticToggle(
            'test_toggle',
            'This is for tests',
            TAG_INTERNAL,
            [NAMESPACE_DOMAIN],
        )
        set_toggle(TEST_TOGGLE.slug, other_domain.name, False, namespace=NAMESPACE_DOMAIN)
        copy_data = {
            'app': self.app.id,
            'domain': other_domain.name,
            'name': 'Copy App',
            'toggles': 'test_toggle',
        }
        with patch('corehq.toggles.all_toggles_by_name', return_value={'test_toggle': TEST_TOGGLE}), \
             mock.patch('corehq.apps.toggle_ui.views.clear_toggle_cache_by_namespace') as mock_clear_cache:
            self.client.post(reverse('copy_app', args=[self.domain]), copy_data)
            mock_clear_cache.assert_called_once_with(NAMESPACE_DOMAIN, other_domain.name)
        self.assertTrue(TEST_TOGGLE.enabled(other_domain.name))


@contextmanager
def apps_modules_setup(test_case):
    """
    Additional setUp and tearDown for get_apps_modules tests
    """
    test_case.app.add_module(Module.new_module("Module0", "en"))
    test_case.app.save()

    test_case.other_app = Application.new_app(test_case.domain, "OtherApp")
    test_case.other_app.add_module(Module.new_module("Module0", "en"))
    test_case.other_app.save()

    test_case.deleted_app = Application.new_app(test_case.domain, "DeletedApp")
    test_case.deleted_app.add_module(Module.new_module("Module0", "en"))
    test_case.deleted_app.save()
    test_case.deleted_app.delete_app()
    test_case.deleted_app.save()  # delete_app() changes doc_type. This save() saves that.

    test_case.linked_app = create_linked_app(test_case.domain, test_case.app.id,
                                             test_case.domain, 'LinkedApp')
    try:
        yield
    finally:
        Application.get_db().delete_doc(test_case.linked_app.id)
        Application.get_db().delete_doc(test_case.deleted_app.id)
        Application.get_db().delete_doc(test_case.other_app.id)


@patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
@es_test(requires=[app_adapter], setup_class=True)
class TestViewGeneric(ViewsBase):
    domain = 'test-view-generic'

    def setUp(self):
        self.client.login(username=self.username, password=self.password)

        self.app = Application.new_app(self.domain, "TestApp")
        self.app.build_spec = BuildSpec.from_string('2.7.0/latest')
        self.module = self.app.add_module(Module.new_module("Module0", "en"))
        self.form = self.app.new_form(
            self.module.id, "Form0", "en",
            attachment=get_simple_form(xmlns='xmlns-0.0'))
        self.app.save()
        app_adapter.index(self.app, refresh=True)  # Send to ES

    def tearDown(self):
        self.app.delete()

    def test_view_app(self, mock1):
        url = reverse('view_app', kwargs={
            'domain': self.domain,
            'app_id': self.app.id,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.keys(), self.expected_keys_app)

    def test_view_module(self, mock1):
        url = reverse('view_module', kwargs={
            'domain': self.domain,
            'app_id': self.app.id,
            'module_unique_id': self.module.unique_id,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.keys(), self.expected_keys_module)

    def test_view_module_legacy(self, mock1):
        url = reverse('view_module_legacy', kwargs={
            'domain': self.domain,
            'app_id': self.app.id,
            'module_id': self.module.id,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.keys(), self.expected_keys_module)

    def test_view_form(self, mock1):
        url = reverse('view_form', kwargs={
            'domain': self.domain,
            'app_id': self.app.id,
            'form_unique_id': self.form.unique_id,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.keys(), self.expected_keys_form)

    def test_view_form_legacy(self, mock1):
        url = reverse('view_form_legacy', kwargs={
            'domain': self.domain,
            'app_id': self.app.id,
            'module_id': self.module.id,
            'form_id': self.form.id,
        })
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context.keys(), self.expected_keys_form)

    expected_keys_app = {
        'None', 'perms', 'practice_users', 'EULA_COMPLIANCE', 'bulk_ui_translation_form',
        'latest_released_version', 'show_live_preview', 'can_view_app_diff', 'bulk_app_translation_form',
        'sms_contacts', 'DEFAULT_MESSAGE_LEVELS', 'jquery_ui', 'PRIVACY_EMAIL', 'user', 'privileges',
        'MAPBOX_ACCESS_TOKEN', 'release_manager', 'WS4REDIS_HEARTBEAT', 'can_send_sms', 'tabs', 'base_template',
        'STATIC_URL', 'tab', 'smart_lang_display_enabled', 'latest_commcare_version', 'MEDIA_URL', 'element_id',
        'app', 'ko', 'BASE_MAIN', 'prompt_settings_url', 'is_remote_app', 'show_biometric', 'linked_name',
        'WEBSOCKET_URI', 'selected_form', 'module', 'MINIMUM_PASSWORD_LENGTH', 'MINIMUM_ZXCVBN_SCORE',
        'SUPPORT_EMAIL', 'app_view_options', 'show_advanced', 'role_version', 'custom_assertions',
        'is_app_settings_page', 'domain_names', 'latest_version_for_build_profiles', 'ANALYTICS_CONFIG',
        'csrf_token', 'LANGUAGE_CODE', 'app_name', 'sub', 'is_saas_environment',
        'selected_module', 'add_ons_layout', 'is_dimagi_environment', 'TIME_ZONE', 'env', 'add_ons',
        'show_shadow_forms', 'can_edit_apps', 'ANALYTICS_IDS', 'active_tab', 'current_url_name',
        'show_release_mode', 'application_profile_url', 'linkable_domains', 'domain_links',
        'show_all_projects_link', 'releases_active', 'settings_active', 'menu', 'allow_report_an_issue', 'app_id',
        'INVOICING_CONTACT_EMAIL', 'False', 'show_mobile_ux_warning', 'IS_DOMAIN_BILLING_ADMIN', 'translations',
        'hq', 'SALES_EMAIL', 'linked_version', 'confirm', 'show_report_modules', 'lang', 'can_view_cloudcare',
        'title_block', 'CUSTOM_LOGO_URL', 'items', 'request', 'messages', 'build_profile_access', 'form', 'error',
        'alerts', 'prompt_settings_form', 'submenu', 'domain', 'enable_update_prompts', 'show_shadow_modules',
        'sentry', 'bulk_ui_translation_upload', 'toggles_dict', 'True', 'full_name', 'latest_build_id',
        'previews_dict', 'copy_app_form', 'show_status_page', 'is_linked_app', 'show_shadow_module_v1',
        'use_bootstrap5', 'limit_to_linked_domains', 'add_ons_privileges', 'LANGUAGE_BIDI', 'page_title_block',
        'LANGUAGES', 'underscore', 'analytics', 'block', 'app_subset', 'restrict_domain_creation',
        'login_template', 'enterprise_mode', 'mobile_ux_cookie_name', 'commcare_hq_names', 'langs',
        'title_context_block', 'timezone', 'helpers', 'has_mobile_workers', 'multimedia_state',
        'bulk_app_translation_upload', 'show_training_modules', 'forloop', 'secure_cookies',
        'IS_ANALYTICS_ENVIRONMENT',
    }

    expected_keys_module = {
        'show_advanced', 'session_endpoints_enabled', 'show_advanced_settings', 'toggles_dict',
        'show_release_mode', 'linked_name', 'linked_version', 'latest_commcare_version',
        'nav_menu_media_specifics', 'user', 'TIME_ZONE', 'domain', 'module_brief', 'timezone', 'active_tab',
        'data_registry_enabled', 'confirm', 'messages', 'releases_active', 'show_status_page',
        'show_search_workflow', 'data_registries', 'label', 'underscore', 'forloop', 'show_shadow_modules',
        'SUPPORT_EMAIL', 'valid_parents_for_child_module', 'parent_case_modules',
        'current_url_name', 'LANGUAGE_BIDI', 'DEFAULT_MESSAGE_LEVELS', 'show_report_modules', 'BASE_MAIN',
        'app_id', 'request', 'MINIMUM_PASSWORD_LENGTH', 'type', 'is_saas_environment', 'show_all_projects_link',
        'enterprise_mode', 'csrf_token', 'WS4REDIS_HEARTBEAT', 'is_dimagi_environment', 'domain_names',
        'IS_DOMAIN_BILLING_ADMIN', 'tabs', 'perms', 'show_training_modules', 'AUDIO_LABEL',
        'show_shadow_module_v1', 'practice_users', 'add_ons', 'module_icon', 'SALES_EMAIL', 'app', 'domain_links',
        'app_subset', 'show_biometric', 'case_list_form_options', 'MINIMUM_ZXCVBN_SCORE', 'ICON_LABEL', 'app_name',
        'linkable_domains', 'alerts', 'show_shadow_forms', 'data_registry_workflow_choices', 'use_bootstrap5',
        'title_block', 'login_template', 'base_template', 'MEDIA_URL', 'lang', 'show_live_preview', 'jquery_ui',
        'latest_version_for_build_profiles', 'edit_name_url', 'case_types', 'js_options', 'ko', 'privileges',
        'settings_active', 'commcare_hq_names', 'add_ons_layout', 'limit_to_linked_domains', 'module', 'True',
        'multimedia', 'MAPBOX_ACCESS_TOKEN', 'helpers', 'all_case_modules', 'LANGUAGES', 'mobile_ux_cookie_name',
        'allow_report_an_issue', 'ANALYTICS_CONFIG', 'custom_icon', 'page_title_block', 'INVOICING_CONTACT_EMAIL',
        'form', 'error', 'previews_dict', 'copy_app_form', 'LANGUAGE_CODE', 'menu', 'add_ons_privileges',
        'shadow_parent', 'restrict_domain_creation', 'show_mobile_ux_warning', 'WEBSOCKET_URI', 'PRIVACY_EMAIL',
        'custom_assertions', 'analytics', 'form_endpoint_options', 'title_context_block', 'secure_cookies',
        'langs', 'details', 'None', 'CUSTOM_LOGO_URL', 'hq', 'selected_form', 'slug', 'env', 'False', 'id',
        'ANALYTICS_IDS', 'STATIC_URL', 'selected_module', 'role_version', 'EULA_COMPLIANCE', 'sentry',
        'case_list_form_not_allowed_reasons', 'child_module_enabled', 'block', 'IS_ANALYTICS_ENVIRONMENT',
    }

    expected_keys_form = {
        'show_advanced', 'is_module_filter_enabled', 'session_endpoints_enabled', 'toggles_dict',
        'show_release_mode', 'linked_name', 'linked_version', 'latest_commcare_version',
        'nav_menu_media_specifics', 'user', 'TIME_ZONE', 'domain', 'case_config_options', 'timezone',
        'root_requires_same_case', 'active_tab', 'confirm', 'messages', 'releases_active', 'show_status_page',
        'form_filter_patterns', 'form_workflows', 'label', 'underscore', 'forloop',
        'SUPPORT_EMAIL', 'current_url_name', 'LANGUAGE_BIDI', 'DEFAULT_MESSAGE_LEVELS', 'show_report_modules',
        'BASE_MAIN', 'xform_languages', 'app_id', 'request', 'allow_usercase', 'MINIMUM_PASSWORD_LENGTH', 'type',
        'is_saas_environment', 'show_all_projects_link', 'enterprise_mode', 'module_is_multi_select', 'csrf_token',
        'WS4REDIS_HEARTBEAT', 'nav_form', 'xform_validation_errored', 'allow_form_filtering',
        'is_dimagi_environment', 'domain_names', 'IS_DOMAIN_BILLING_ADMIN', 'tabs', 'perms',
        'show_training_modules', 'AUDIO_LABEL', 'show_shadow_module_v1', 'practice_users', 'add_ons',
        'module_icon', 'custom_instances', 'SALES_EMAIL', 'app', 'domain_links', 'form_errors', 'app_subset',
        'show_biometric', 'MINIMUM_ZXCVBN_SCORE', 'ICON_LABEL', 'app_name', 'linkable_domains', 'alerts',
        'show_shadow_forms', 'use_bootstrap5', 'form_icon', 'title_block', 'login_template', 'base_template',
        'MEDIA_URL', 'lang', 'show_live_preview', 'jquery_ui', 'latest_version_for_build_profiles',
        'edit_name_url', 'ko', 'privileges', 'settings_active', 'commcare_hq_names', 'add_ons_layout',
        'limit_to_linked_domains', 'module', 'is_case_list_form', 'True', 'multimedia', 'MAPBOX_ACCESS_TOKEN',
        'xform_validation_missing', 'helpers', 'LANGUAGES', 'mobile_ux_cookie_name', 'allow_report_an_issue',
        'ANALYTICS_CONFIG', 'is_training_module', 'custom_icon', 'page_title_block', 'INVOICING_CONTACT_EMAIL',
        'form', 'error', 'previews_dict', 'copy_app_form', 'LANGUAGE_CODE', 'menu', 'add_ons_privileges',
        'restrict_domain_creation', 'show_mobile_ux_warning', 'WEBSOCKET_URI', 'PRIVACY_EMAIL',
        'is_allowed_to_be_release_notes_form', 'custom_assertions', 'analytics', 'title_context_block', 'id',
        'secure_cookies', 'langs', 'None', 'CUSTOM_LOGO_URL', 'hq', 'allow_form_copy', 'selected_form', 'slug',
        'env', 'False', 'ANALYTICS_IDS', 'STATIC_URL', 'selected_module', 'role_version', 'is_usercase_in_use',
        'module_loads_registry_case', 'EULA_COMPLIANCE', 'sentry', 'show_shadow_modules', 'show_custom_ref',
        'block', 'IS_ANALYTICS_ENVIRONMENT',
    }


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
            HTTP_AUTHORIZATION=f"ApiKey {self.web_user.username}:{self.web_user_api_key.plaintext_key}",
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
                self.url, HTTP_AUTHORIZATION=f"ApiKey :{self.web_user_api_key.plaintext_key}"
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


def test_doctests():
    import corehq.apps.app_manager.views.view_generic as module

    results = doctest.testmod(module)
    assert results.failed == 0
