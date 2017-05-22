from datetime import datetime, timedelta
from django.test import TestCase

from corehq.apps.groups.models import Group

from corehq.warehouse.dbaccessors import get_group_ids_by_last_modified


class TestDbAccessors(TestCase):
    domain = 'warehouse'

    @classmethod
    def setUpClass(cls):
        cls.g1 = Group(domain=cls.domain, name='group')
        cls.g1.save()

        cls.g2 = Group(domain=cls.domain, name='group')
        cls.g2.save()
        cls.g2.soft_delete()

    @classmethod
    def tearDownClass(cls):
        cls.g1.delete()
        cls.g2.delete()

    def test_get_group_ids_by_last_modified(self):
        start = datetime.utcnow() - timedelta(days=3)
        end = datetime.utcnow() + timedelta(days=3)

        self.assertEqual(
            set(get_group_ids_by_last_modified(start, end)),
            set([self.g1._id, self.g2._id]),
        )

        self.assertEqual(
            set(get_group_ids_by_last_modified(start, end - timedelta(days=4))),
            set(),
        )
