from __future__ import print_function, unicode_literals

from django.test import TestCase

from corehq.apps.domain.models import Domain
from corehq.apps.domain.calculations import all_domain_stats, calced_props

class DomainCalculatedPropertiesTest(TestCase):

    def setUp(self):
        self.domain = Domain(name='test')
        self.domain.save()

    def tearDown(self):
        self.domain.delete()

    def test_sanity(self):
        all_stats = all_domain_stats()
        props = calced_props(self.domain.name, self.domain._id, all_stats)
        self.assertFalse(props['cp_has_app'])
