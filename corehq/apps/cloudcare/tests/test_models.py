import uuid
from django.test import TestCase

from corehq.apps.cloudcare.dbaccessors import get_application_access_for_domain
from corehq.apps.cloudcare.models import ApplicationAccess, SQLAppGroup


class MockApplication(object):
    def __init__(self, domain, name):
        self.domain = domain
        self.name = name
        self._id = uuid.uuid4().hex

    @property
    def get_id(self):
        return self._id


class ModelsTest(TestCase):
    domain = 'application-access'

    @classmethod
    def tearDownClass(cls):
        ApplicationAccess.objects.all().delete()
        get_application_access_for_domain.clear(cls.domain)
        super().tearDownClass()

    def test_application_access(self):
        app1 = MockApplication(self.domain, "One")
        app2 = MockApplication(self.domain, "Two")
        app3 = MockApplication(self.domain, "Three")
        app4 = MockApplication(self.domain, "Four")

        o = get_application_access_for_domain(self.domain)
        o.sqlappgroup_set.set([
            SQLAppGroup(app_id=app1._id, group_id="321"),
            SQLAppGroup(app_id=app2._id, group_id="432"),
            SQLAppGroup(app_id=app3._id, group_id="543"),
        ], bulk=False)
        o.save()

        refreshed = get_application_access_for_domain(self.domain)
        self.assertEqual(o.domain, refreshed.domain)
        self.assertEqual(3, refreshed.sqlappgroup_set.count())

        self.assertEqual(o.get_template_json([app1, app2, app4]), {
            "domain": self.domain,
            "restrict": False,
            "app_groups": [
                {
                    "app_id": app4._id,
                    "group_id": None,
                },
                {
                    "app_id": app1._id,
                    "group_id": "321",
                },
                {
                    "app_id": app2._id,
                    "group_id": "432",
                },
            ],
        })
