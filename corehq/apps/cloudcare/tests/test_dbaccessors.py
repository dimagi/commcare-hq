from django.test import TestCase
from corehq.apps.cloudcare.dbaccessors import get_application_access_for_domain
from corehq.apps.cloudcare.models import ApplicationAccess


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
