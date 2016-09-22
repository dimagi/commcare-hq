import uuid
from django.test import TestCase
from corehq.apps.domain.shortcuts import create_domain
from corehq.form_processor.utils.general import get_local_domain_sql_backend_override, \
    set_local_domain_sql_backend_override, should_use_sql_backend, clear_local_domain_sql_backend_override


class UseSqlBackendTest(TestCase):

    def test_local_domain_sql_backend_override_initial_none(self):
        self.assertIsNone(get_local_domain_sql_backend_override(uuid.uuid4().hex))

    def test_local_domain_sql_backend_override(self):
        domain_name = uuid.uuid4().hex
        set_local_domain_sql_backend_override(domain_name)
        self.assertTrue(get_local_domain_sql_backend_override(domain_name))

        clear_local_domain_sql_backend_override(domain_name)
        self.assertFalse(get_local_domain_sql_backend_override(domain_name))

    def test_test_local_domain_sql_backend_override_overrides(self):
        domain_name = uuid.uuid4().hex
        create_domain(domain_name)
        self.assertFalse(should_use_sql_backend(domain_name))

        set_local_domain_sql_backend_override(domain_name)
        self.assertTrue(should_use_sql_backend(domain_name))

        clear_local_domain_sql_backend_override(domain_name)
        self.assertFalse(should_use_sql_backend(domain_name))
