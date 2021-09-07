from unittest.mock import patch, Mock

from django.test import SimpleTestCase, TestCase

from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.exceptions import RegistryAccessException
from corehq.apps.registry.helper import DataRegistryHelper, _get_case_descendants, _get_case_ancestors
from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.schema import RegistrySchemaBuilder
from corehq.apps.registry.tests.utils import create_registry_for_test
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.tests.utils import run_with_sql_backend, FormProcessorTestUtils


class TestDataRegistryHelper(SimpleTestCase):
    def setUp(self):
        self.registry = DataRegistry(
            schema=[{"case_type": "a"}]
        )
        self.registry.get_granted_domains = _mock_get_granted_domain
        self.helper = DataRegistryHelper("domain1", "registry_slug")
        self.helper.__dict__["registry"] = self.registry  # prime cached property

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


@run_with_sql_backend
class TestGetCaseHierarchy(TestCase):
    domain = 'data-registry-case-hierarchy'

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user("marg", "hairspray")
        cls.registry = create_registry_for_test(cls.user, cls.domain)
        cls.registry.schema = RegistrySchemaBuilder(["grandparent", "parent", "child", "extension"]).build()
        cls.registry.save()

        cls.helper = DataRegistryHelper(cls.domain, cls.registry.slug)

        cls.host_case_id = 'springfield'
        cls.grand_parent_case_id = 'mona'
        cls.parent_case_id = 'homer'
        cls.child_case_id = 'bart'
        cls.extension_case_id = 'beer'
        host_case = CaseStructure(
            case_id=cls.host_case_id,
            attrs={'create': True, 'case_type': 'town'},
        )
        grand_parent_case = CaseStructure(
            case_id=cls.grand_parent_case_id,
            attrs={'create': True, 'case_type': 'grandparent'},
        )

        parent_case = CaseStructure(
            case_id=cls.parent_case_id,
            attrs={'create': True, 'case_type': 'parent'},
            indices=[
                CaseIndex(grand_parent_case, identifier='parent'),
                CaseIndex(host_case, identifier='host', relationship='extension'),
            ],
        )

        child_case = CaseStructure(
            case_id=cls.child_case_id,
            attrs={'create': True, 'case_type': 'child'},
            indices=[CaseIndex(
                parent_case,
                identifier='parent',
            )],
        )

        extension_case = CaseStructure(
            case_id=cls.extension_case_id,
            attrs={'create': True, 'case_type': 'extension'},
            indices=[CaseIndex(
                parent_case,
                identifier='host',
                relationship='extension',
            )],
            walk_related=False
        )
        cls.cases = CaseFactory(cls.domain).create_or_update_cases([child_case, extension_case])

    @classmethod
    def tearDownClass(cls):
        cls.user.delete()
        cls.registry.delete()
        FormProcessorTestUtils.delete_all_sql_forms(cls.domain)
        FormProcessorTestUtils.delete_all_sql_cases(cls.domain)
        super().tearDownClass()

    def test_get_case_hierarchy(self):
        cases = self.helper.get_case_hierarchy(CaseAccessorSQL.get_case(self.parent_case_id))
        self.assertEqual({case.case_id for case in cases}, {
            self.host_case_id, self.grand_parent_case_id, self.parent_case_id,
            self.child_case_id, self.extension_case_id
        })

    def test_get_ancestors_extension(self):
        cases = _get_case_ancestors(CaseAccessorSQL.get_case(self.extension_case_id))
        self.assertEqual({case.case_id for case in cases}, {
            self.host_case_id, self.grand_parent_case_id, self.parent_case_id,
        })

    def test_get_ancestors_child(self):
        cases = _get_case_ancestors(CaseAccessorSQL.get_case(self.child_case_id))
        self.assertEqual({case.case_id for case in cases}, {
            self.host_case_id, self.grand_parent_case_id, self.parent_case_id,
        })

    def test_get_descendants_parent(self):
        cases = _get_case_descendants(CaseAccessorSQL.get_case(self.grand_parent_case_id))
        self.assertEqual({case.case_id for case in cases}, {
            self.parent_case_id, self.child_case_id, self.extension_case_id
        })

    def test_get_descendants_host(self):
        cases = _get_case_descendants(CaseAccessorSQL.get_case(self.host_case_id))
        self.assertEqual({case.case_id for case in cases}, {
            self.parent_case_id, self.child_case_id, self.extension_case_id
        })


def _mock_get_granted_domain(domain):
    return {"domain1"}


def _mock_case(case_type, domain):
    return Mock(type=case_type, domain=domain, spec_set=["type", "domain"])
