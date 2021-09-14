import uuid
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.utils.general import should_use_sql_backend


class UseSqlBackendTest(TestCase):

    def test_should_use_sql_backend(self):
        domain_name = uuid.uuid4().hex
        domain_obj = create_domain(domain_name)
        self.addCleanup(domain_obj.delete)
        self.assertTrue(should_use_sql_backend(domain_name))
