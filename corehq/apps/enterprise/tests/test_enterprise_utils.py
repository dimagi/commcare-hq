from django.test import TestCase

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.enterprise.tests.utils import create_enterprise_permissions
from corehq.apps.enterprise.utils import get_enterprise_domains


class TestEnterpriseUtils(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'domain'
        cls.domain_obj = create_domain(cls.domain)
        cls.source_domain = 'source-domain'
        cls.source_domain_obj = create_domain(cls.source_domain)
        create_enterprise_permissions("hello@world.com", cls.source_domain, [cls.domain])

    def setUp(self):
        super(TestEnterpriseUtils, self).setUp()

    @classmethod
    def tearDownClass(cls):
        cls.domain_obj.delete()
        cls.source_domain_obj.delete()
        super(TestEnterpriseUtils, cls).tearDownClass()

    def test_get_enterprise_domains(self):
        self.assertEqual(
            set(['source-domain']),
            set(get_enterprise_domains(self.source_domain))
        )
        self.assertEqual(
            set(['domain', 'source-domain']),
            set(get_enterprise_domains(self.domain))
        )
