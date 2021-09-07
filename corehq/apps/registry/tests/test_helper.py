from unittest.mock import patch, Mock

from django.test import SimpleTestCase

from corehq.apps.registry.exceptions import RegistryAccessException
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.registry.models import DataRegistry
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.exceptions import CaseNotFound


class TestDataRegistryHelper(SimpleTestCase):
    def setUp(self):
        self.registry = DataRegistry(
            schema=[{"case_type": "a"}]
        )
        self.registry.get_granted_domains = _mock_get_granted_domain
        self.helper = DataRegistryHelper("domain1", registry=self.registry)

        self.log_data_access_patch = patch.object(self.helper, "log_data_access")
        self.log_data_access = self.log_data_access_patch.start()

    def tearDown(self):
        self.log_data_access_patch.stop()

    def test_get_case(self):
        mockCase = _mock_case("a", "domain1")
        with patch.object(CaseAccessorSQL, 'get_case', return_value=mockCase):
            case = self.helper.get_case("case1", "a", "user", "app")
        self.assertEqual(case, mockCase)
        self.log_data_access.assert_called_with("user", "domain1", "app", filters={
            "case_type": "a",
            "case_id": "case1"
        })

    def test_get_case_type_not_in_registry(self):
        with self.assertRaisesMessage(RegistryAccessException, "'other-type' not available in registry"):
            self.helper.get_case("case1", "other-type", "user", "app")
        self.log_data_access.not_called()

    def test_get_case_not_found(self):
        with self.assertRaises(CaseNotFound), \
             patch.object(CaseAccessorSQL, 'get_case', side_effect=CaseNotFound):
            self.helper.get_case("case1", "a", "user", "app")
        self.log_data_access.not_called()

    def test_get_case_type_mismatch(self):
        mockCase = _mock_case("other-type", "domain1")
        with self.assertRaisesMessage(CaseNotFound, "Case type mismatch"), \
             patch.object(CaseAccessorSQL, 'get_case', return_value=mockCase):
            self.helper.get_case("case1", "a", "user", "app")
        self.log_data_access.not_called()

    def test_get_case_domain_not_in_registry(self):
        mockCase = _mock_case("a", "other-domain")
        with self.assertRaisesMessage(RegistryAccessException, "Data not available in registry"), \
             patch.object(CaseAccessorSQL, 'get_case', return_value=mockCase):
            self.helper.get_case("case1", "a", "user", "app")
        self.log_data_access.not_called()


def _mock_get_granted_domain(domain):
    return {"domain1"}


def _mock_case(case_type, domain):
    return Mock(type=case_type, domain=domain, spec_set=["type", "domain"])
