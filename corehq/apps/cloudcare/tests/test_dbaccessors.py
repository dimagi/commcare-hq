from __future__ import absolute_import
from __future__ import unicode_literals
from django.test import TestCase
from corehq.apps.cloudcare.dbaccessors import get_application_access_for_domain, get_app_id_from_hash
from corehq.apps.cloudcare.models import ApplicationAccess
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.signals import app_post_save
from corehq.util.context_managers import drop_connected_signals


class DBAccessorsTest(TestCase):

    def test_get_application_access_for_domain(self):
        application_access_objects = []
        domain = 'application-access-dbaccessors'
        try:
            self.assertIsNone(get_application_access_for_domain(domain))
            o = ApplicationAccess(domain=domain)
            o.save()
            application_access_objects.append(o)
            self.assertEqual(
                o.to_json(),
                get_application_access_for_domain(domain).to_json()
            )
            o = ApplicationAccess(domain=domain)
            o.save()
            application_access_objects.append(o)
            self.assertIn(
                get_application_access_for_domain(domain).to_json(),
                [o.to_json() for o in application_access_objects]
            )
        finally:
            ApplicationAccess.get_db().bulk_delete(application_access_objects)


class TestGetAppIdFromHash(TestCase):
    domain = 'get-app-id-from-hash'

    def setUp(self):
        factory = AppFactory(domain=self.domain)
        self.app = factory.app
        self.app.anonymous_cloudcare_enabled = True

        factory = AppFactory(domain=self.domain)
        self.decoy = factory.app
        self.decoy.anonymous_cloudcare_enabled = False

        with drop_connected_signals(app_post_save):
            self.app.save()
            self.decoy.save()

    def tearDown(self):
        self.app.delete()
        self.decoy.delete()

    def test_get_app_id_from_hash(self):
        self.assertIsNotNone(self.app.anonymous_cloudcare_hash)

        app_id = get_app_id_from_hash(self.domain, self.app.anonymous_cloudcare_hash)
        self.assertEqual(app_id, self.app._id)

    def test_get_app_id_from_hash_non_existant(self):
        # Should fail because it's the wrong hash
        app_id = get_app_id_from_hash(self.domain, 'non-existant')
        self.assertIsNone(app_id)

        # Should fail because it's the wrong domain
        app_id = get_app_id_from_hash('wrong-domain', self.app.anonymous_cloudcare_hash)
        self.assertIsNone(app_id)

        # Should fail because it's anonymous cloudcare is not enabled
        app_id = get_app_id_from_hash(self.decoy.domain, self.decoy.anonymous_cloudcare_hash)
        self.assertIsNone(app_id)
