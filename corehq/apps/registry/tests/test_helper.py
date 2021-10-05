from unittest.mock import patch, Mock

from django.test import SimpleTestCase, TestCase

from casexml.apps.case.mock import CaseStructure, CaseIndex, CaseFactory
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.registry.exceptions import RegistryAccessException
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.registry.models import DataRegistry
from corehq.apps.registry.schema import RegistrySchemaBuilder
from corehq.apps.registry.tests.utils import create_registry_for_test
from corehq.apps.users.models import Permissions
from corehq.form_processor.backends.sql.dbaccessors import CaseAccessorSQL
from corehq.form_processor.exceptions import CaseNotFound
from corehq.form_processor.tests.utils import FormProcessorTestUtils


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
        mock_case = _mock_case("a", "domain1")
        with patch.object(CaseAccessorSQL, 'get_case', return_value=mock_case):
            case = self.helper.get_case("case1", "a", _mock_user(), "app")
        self.assertEqual(case, mock_case)
        self.log_data_access.assert_called_with("user", "domain1", "app", filters={
            "case_type": "a",
            "case_id": "case1"
        })

    def test_get_case_type_not_in_registry(self):
        mock_case = _mock_case("other-type", "domain1")
        with patch.object(CaseAccessorSQL, 'get_case', return_value=mock_case), \
             self.assertRaisesMessage(RegistryAccessException, "'other-type' not available in registry"):
            self.helper.get_case("case1", "other-type", _mock_user(), "app")
        self.log_data_access.not_called()

    def test_get_case_not_found(self):
        with self.assertRaises(CaseNotFound), \
             patch.object(CaseAccessorSQL, 'get_case', side_effect=CaseNotFound):
            self.helper.get_case("case1", "a", _mock_user(), "app")
        self.log_data_access.not_called()

    def test_get_case_type_mismatch(self):
        mock_case = _mock_case("other-type", "domain1")
        with self.assertRaisesMessage(CaseNotFound, "Case type mismatch"), \
             patch.object(CaseAccessorSQL, 'get_case', return_value=mock_case):
            self.helper.get_case("case1", "a", _mock_user(), "app")
        self.log_data_access.not_called()

    def test_get_case_domain_not_in_registry(self):
        mock_case = _mock_case("a", "other-domain")
        with self.assertRaisesMessage(RegistryAccessException, "Data not available in registry"), \
             patch.object(CaseAccessorSQL, 'get_case', return_value=mock_case):
            self.helper.get_case("case1", "a", _mock_user(), "app")
        self.log_data_access.not_called()

    def test_get_case_access_to_current_domain_allowed_even_if_user_has_no_permission(self):
        mock_case = _mock_case("a", "domain1")
        mock_user = _mock_user(has_permission=False)
        with patch.object(CaseAccessorSQL, 'get_case', return_value=mock_case):
            self.helper.get_case("case1", "a", mock_user, "app")
        self.log_data_access.assert_called_with("user", "domain1", "app", filters={
            "case_type": "a",
            "case_id": "case1"
        })

    def test_get_case_access_to_other_domain_not_allowed_if_user_has_no_permission(self):
        mock_case = _mock_case("a", "domain2")
        mock_user = _mock_user(has_permission=False)
        with self.assertRaisesMessage(RegistryAccessException, "User not permitted to access registry data"),\
             patch.object(CaseAccessorSQL, 'get_case', return_value=mock_case):
            self.helper.get_case("case1", "a", mock_user, "app")

    def test_get_case_access_to_other_domain_allowed_if_user_has_permission(self):
        mock_case = _mock_case("a", "domain2")
        mock_user = _mock_user(has_permission=True)
        with patch.object(CaseAccessorSQL, 'get_case', return_value=mock_case):
            self.helper.get_case("case1", "a", mock_user, "app")
        self.log_data_access.assert_called_with("user", "domain2", "app", filters={
            "case_type": "a",
            "case_id": "case1"
        })


class TestGetCaseHierarchy(TestCase):
    domain = 'data-registry-case-hierarchy'

    @classmethod
    def setUpTestData(cls):
        cls.user = create_user("marg", "hairspray")
        cls.registry = create_registry_for_test(cls.user, cls.domain)
        cls.registry.schema = RegistrySchemaBuilder(["grandparent", "parent", "child", "extension"]).build()
        cls.registry.save()

        cls.helper = DataRegistryHelper(cls.domain, cls.registry.slug)

        """
        springfield     <--ext--
        mona            <-------
        abraham(closed) <------- homer <------- bart
                                       <--ext-- beer
       """

        cls.host_case_id = 'springfield'
        cls.grand_parent_case_id = 'mona'
        cls.grand_parent_case_id_closed = 'abraham'
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

        grand_parent_case_closed = CaseStructure(
            case_id=cls.grand_parent_case_id_closed,
            attrs={'create': True, 'case_type': 'grandparent', 'close': True},
        )

        parent_case = CaseStructure(
            case_id=cls.parent_case_id,
            attrs={'create': True, 'case_type': 'parent'},
            indices=[
                CaseIndex(grand_parent_case, identifier='mother'),
                CaseIndex(grand_parent_case_closed, identifier='father'),
                CaseIndex(host_case, identifier='host', relationship='extension'),
            ],
        )

        child_case = CaseStructure(
            case_id=cls.child_case_id,
            attrs={'create': True, 'case_type': 'child'},
            indices=[CaseIndex(parent_case, identifier='parent')],
        )

        extension_case = CaseStructure(
            case_id=cls.extension_case_id,
            attrs={'create': True, 'case_type': 'extension'},
            indices=[CaseIndex(parent_case, identifier='host', relationship='extension')],
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

    @patch.object(DataRegistryHelper, '_check_user_has_access', new=Mock())
    def test_get_case_hierarchy(self):
        cases = self.helper.get_case_hierarchy(None, CaseAccessorSQL.get_case(self.parent_case_id))
        self.assertEqual({case.case_id for case in cases}, {
            self.grand_parent_case_id_closed, self.host_case_id, self.grand_parent_case_id,
            self.parent_case_id, self.extension_case_id
        })


def _mock_get_granted_domain(domain):
    return {"domain1", "domain2"}


def _mock_case(case_type, domain):
    return Mock(type=case_type, domain=domain, spec_set=["type", "domain"])


def _mock_user(has_permission=True):
    mock_role = Mock(permissions=Permissions(view_data_registry_contents=has_permission))
    return Mock(get_role=Mock(return_value=mock_role), get_django_user=Mock(return_value="user"))
