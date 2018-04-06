from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from mock import patch

from couchdbkit import ResourceNotFound

from corehq.apps.app_manager.exceptions import PracticeUserException
from corehq.apps.app_manager.models import Application, BuildProfile
from corehq.apps.app_manager.views.utils import unset_practice_mode_configured_apps, \
    get_practice_mode_configured_apps
from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.ota.utils import turn_on_demo_mode, turn_off_demo_mode
from corehq.apps.users.models import CommCareUser

from .app_factory import AppFactory
from .util import TestXmlMixin


class TestPracticeUserRestore(TestCase, TestXmlMixin):
    """Tests for Practice Mobile Worker feature"""
    file_path = ('data',)

    @classmethod
    def setUpClass(cls):
        super(TestPracticeUserRestore, cls).setUpClass()
        cls.domain = "practice-user-domain"

        cls.project = create_domain(cls.domain)
        cls.user = CommCareUser.create(cls.domain, 'test@main-domain.commcarehq.org', 'secret')

    def setUp(self):
        self.factory = AppFactory(build_version='2.30.0', domain=self.domain)
        module, form = self.factory.new_basic_module('register', 'case')
        form.source = self.get_xml('very_simple_form')
        self.factory.app.save()

    def tearDown(self):
        self.factory.app.delete()
        turn_off_demo_mode(self.user)

    @classmethod
    def tearDownClass(cls):
        cls.project.delete()
        super(TestPracticeUserRestore, cls).tearDownClass()

    @staticmethod
    def _get_restore_resource(version, build_profile_id=None):
        extra = "?profile={id}".format(id=build_profile_id) if build_profile_id else ""
        return """
        <partial>
        <user-restore>
           <resource id="practice-user-restore" version="{version}" descriptor="practice user restore">
             <location authority="local">./practice_user_restore.xml</location>
             <location authority="remote">./practice_user_restore.xml{extra}</location>
           </resource>
        </user-restore>
        </partial>
        """.format(version=version, extra=extra)

    @patch('corehq.apps.app_manager.models.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_app_specific(self, mock):
        turn_on_demo_mode(self.user, self.domain)
        app = self.factory.app
        app.practice_mobile_worker_id = self.user._id

        # check suit contains user-restore resource
        self.assertXmlPartialEqual(
            self._get_restore_resource(self.user.demo_restore_id),
            app.create_suite(),
            "./user-restore"
        )
        # check 'files/practice_user_restore.xml' is included in the build files
        app.create_build_files(save=True)
        app.save()
        self.assertTrue(app.lazy_fetch_attachment('files/practice_user_restore.xml'))

    @patch('corehq.apps.app_manager.models.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_profile_specific(self, mock):
        turn_on_demo_mode(self.user, self.domain)
        app = self.factory.app
        build_profile_id = "some_uuid"
        app.build_profiles[build_profile_id] = BuildProfile(
            langs=['en'], name='en-profile', practice_mobile_worker_id=self.user._id
        )

        self.assertXmlPartialEqual(
            self._get_restore_resource(self.user.demo_restore_id, build_profile_id),
            app.create_suite(build_profile_id=build_profile_id),
            "./user-restore"
        )
        app.create_build_files(save=True, build_profile_id=build_profile_id)
        app.save()
        self.assertTrue(app.lazy_fetch_attachment('files/{profile}/practice_user_restore.xml'.format(
            profile=build_profile_id
        )))

    @patch('corehq.apps.app_manager.models.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_bad_config(self, mock):
        # if the user set as practice user for an app is not practice user, build should raise error
        app = self.factory.app
        app.practice_mobile_worker_id = self.user._id

        self.assertIn(
            'practice user config error',
            [error['type'] for error in app.validate_app()]
        )
        with self.assertRaises(PracticeUserException):
            app.create_all_files()

    @patch('corehq.apps.app_manager.models.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_update_user_restore(self, mock):
        # updating user restore should result in version change in restore resource
        #   so that CommCare mobile will refetch the resource
        turn_on_demo_mode(self.user, self.domain)
        app = self.factory.app
        app.practice_mobile_worker_id = self.user._id
        app.save()

        self.assertXmlPartialEqual(
            self._get_restore_resource(self.user.demo_restore_id),
            app.create_suite(),
            "./user-restore"
        )

        version_before = self.user.demo_restore_id
        turn_off_demo_mode(self.user)
        turn_on_demo_mode(self.user, self.domain)
        version_after = self.user.demo_restore_id
        self.assertNotEqual(version_before, version_after)

        # refetch so that memoized app.get_practice_user gets busted`
        app = Application.get(app._id)
        app.build_spec.version = '2.30'  # for some reason, this gets set to an old version, after refetch
        self.assertXmlPartialEqual(
            self._get_restore_resource(version_after),
            app.create_suite(),
            "./user-restore"
        )

    @patch('corehq.apps.app_manager.models.domain_has_privilege', lambda x, y: True)
    @patch('corehq.apps.app_manager.models.validate_xform', return_value=None)
    def test_commcare_version(self, mock):
        turn_on_demo_mode(self.user, self.domain)
        app = self.factory.app
        app.practice_mobile_worker_id = self.user._id
        app.build_spec.version = '2.20.0'  # less than supported version
        app.save()

        self.assertXmlDoesNotHaveXpath(
            app.create_suite(),
            "./user-restore"
        )

        app.create_build_files(save=True)
        app.save()
        with self.assertRaises(ResourceNotFound):
            self.assertTrue(app.lazy_fetch_attachment('files/practice_user_restore.xml'))


class TestUnsetPracticeUserUtil(TestCase):

    def setUp(self):
        # app with no practice user
        self.domain = "test-domain"
        self.app1 = AppFactory(build_version='2.30.0', domain=self.domain).app

        self.app2 = AppFactory(build_version='2.30.0', domain=self.domain).app
        self.app2.practice_mobile_worker_id = "user1"

        self.app3 = AppFactory(build_version='2.30.0', domain=self.domain).app
        self.app3.build_profiles['build1'] = BuildProfile(
            langs=['en'], name='en-profile', practice_mobile_worker_id="user1"
        )
        self.app3.build_profiles['build2'] = BuildProfile(
            langs=['en'], name='en-profile', practice_mobile_worker_id="user2"
        )
        self.apps = [self.app1, self.app2, self.app3]
        for app in self.apps:
            app.save()

    def reset_apps(self):
        self.app1 = Application.get(self.app1.get_id)
        self.app2 = Application.get(self.app2.get_id)
        self.app3 = Application.get(self.app3.get_id)

    def tearDown(self):
        for app in self.apps:
            app.delete()

    def app_to_ids(self, apps):
        return set([app.get_id for app in apps])

    def test_get_practice_mode_apps(self):
        self.assertEqual(
            {app.get_id for app in get_practice_mode_configured_apps(self.domain)},
            {self.app2.get_id, self.app3.get_id}
        )
        self.assertEqual(
            {app.get_id for app in get_practice_mode_configured_apps(self.domain, 'user2')},
            {self.app3.get_id}
        )

    def test_unset_all(self):
        unset_practice_mode_configured_apps(self.domain)
        self.reset_apps()

        self.assertEqual(self.app1.practice_mobile_worker_id, None)
        self.assertEqual(self.app2.practice_mobile_worker_id, None)
        self.assertEqual(self.app3.build_profiles['build1'].practice_mobile_worker_id, None)
        self.assertEqual(self.app3.build_profiles['build2'].practice_mobile_worker_id, None)

    def test_unset_by_user(self):
        unset_practice_mode_configured_apps(self.domain, "user2")
        self.reset_apps()
        self.assertEqual(self.app1.practice_mobile_worker_id, None)
        self.assertEqual(self.app2.practice_mobile_worker_id, 'user1')
        self.assertEqual(self.app3.build_profiles['build1'].practice_mobile_worker_id, 'user1')
        self.assertEqual(self.app3.build_profiles['build2'].practice_mobile_worker_id, None)
