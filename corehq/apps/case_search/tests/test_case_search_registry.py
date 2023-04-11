import uuid
from unittest import mock

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock, IndexAttrs

from corehq.apps.app_manager.models import (
    CaseSearch,
    CaseSearchProperty,
    DetailColumn,
)
from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.case_search.const import COMMCARE_PROJECT
from corehq.apps.case_search.models import (
    CaseSearchConfig,
    SearchCriteria,
    criteria_dict_to_criteria_list,
)
from corehq.apps.case_search.utils import (
    _get_helper,
    get_case_search_results,
    get_primary_case_search_results,
    get_and_tag_related_cases,
)
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    es_test,
)
from corehq.apps.registry.helper import DataRegistryHelper
from corehq.apps.registry.tests.utils import (
    Grant,
    Invitation,
    create_registry_for_test,
)
from corehq.apps.users.models import HqPermissions
from corehq.form_processor.tests.utils import FormProcessorTestUtils


def case(name, type_, properties):
    return CaseBlock(
        case_id=str(uuid.uuid4()),
        case_type=type_,
        case_name=name,
        create=True,
        update=properties,
    )


def parent_and_child_cases(parent_name, child_name):
    parent_id = str(uuid.uuid4())
    return [
        CaseBlock(
            case_id=parent_id,
            case_type='creator',
            case_name=parent_name,
            create=True,
        ),
        CaseBlock(
            case_id=str(uuid.uuid4()),
            case_type='creative_work',
            case_name=child_name,
            create=True,
            index={'parent': IndexAttrs('creator', parent_id, 'child')},
        )
    ]


def get_app_with_case_search(domain):
    factory = AppFactory(domain=domain)
    for case_type, fields in [
            ('person', ['name']),
            ('creative_work', ['name', 'parent/name']),
    ]:
        module, _ = factory.new_basic_module(case_type, case_type)
        module.search_config = CaseSearch(
            properties=[CaseSearchProperty(name=field) for field in fields]
        )
        module.case_details.short.columns = [
            DetailColumn(format='plain', field=field, header={'en': field}, model=case_type)
            for field in fields
        ]
    return factory.app


patch_get_app_cached = mock.patch('corehq.apps.case_search.utils.get_app_cached',
                                  lambda domain, _: get_app_with_case_search(domain))


@es_test(requires=[case_search_adapter], setup_class=True)
@mock.patch.object(DataRegistryHelper, '_check_user_has_access', new=mock.Mock())
class TestCaseSearchRegistry(TestCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = create_user("admin", "123")
        cls.domain_1 = "jane-the-virgin"
        cls.setup_domain(cls.domain_1, [
            case("Jane", 'person', {"family": "Villanueva"}),
            case("Xiomara", 'person', {"family": "Villanueva"}),
            case("Alba", 'person', {"family": "Villanueva"}),
            case("Rogelio", 'person', {"family": "de la Vega"}),
            case("Jane", 'person', {"family": "Ramos"}),
        ] + parent_and_child_cases(
            "Jennie Snyder Urman",
            "Jane the Virgin",
        ))
        cls.domain_2 = "jane-eyre"
        cls.setup_domain(cls.domain_2, [
            case("Jane", 'person', {"family": "Eyre"}),
            case("Sarah", 'person', {"family": "Reed"}),
            case("John", 'person', {"family": "Reed"}),
            case("Eliza", 'person', {"family": "Reed"}),
            case("Georgiana", 'person', {"family": "Reed"}),
        ] + parent_and_child_cases(
            "Charlotte Brontë",
            "Jane Eyre",
        ))
        cls.domain_3 = "janes-addiction"
        cls.setup_domain(cls.domain_3, [
            case("Jane", 'person', {"family": "Villanueva"}),
            case("Perry", 'person', {"family": "Farrell"}),
            case("Dave", 'person', {"family": "Navarro"}),
            case("Stephen", 'person', {"family": "Perkins"}),
            case("Chris", 'person', {"family": "Chaney"}),
        ])

        cls.registry_slug = create_registry_for_test(
            cls.user,
            cls.domain_1,
            invitations=[
                Invitation(cls.domain_2),
                Invitation(cls.domain_3),
            ],
            grants=[
                Grant(cls.domain_1, [cls.domain_2]),
                Grant(cls.domain_2, [cls.domain_1]),
                Grant(cls.domain_3, [cls.domain_1]),
            ],
            name="reg1",
            case_types=["person", "creative_work"]
        ).slug

    @classmethod
    def setup_domain(cls, domain, cases):
        CaseSearchConfig.objects.create(pk=domain, enabled=True)
        case_search_es_setup(domain, cases)

    @classmethod
    def tearDownClass(cls):
        FormProcessorTestUtils.delete_all_cases()
        super().tearDownClass()

    def _run_query(self, domain, case_types, criteria_dict, registry_slug):
        criteria = criteria_dict_to_criteria_list(criteria_dict)
        results = get_case_search_results(domain, case_types, criteria, registry_slug=registry_slug)
        return [(case.name, case.domain) for case in results]

    def test_query_all_domains_in_registry(self):
        # Domain 1 has access to all three domains
        results = self._run_query(
            self.domain_1,
            ['person'],
            {"name": "Jane"},
            self.registry_slug,
        )
        self.assertItemsEqual([
            ("Jane", self.domain_1),
            ("Jane", self.domain_1),
            ("Jane", self.domain_2),
            ("Jane", self.domain_3),
        ], results)

    def test_case_property_query(self):
        results = self._run_query(
            self.domain_1,
            ['person'],
            {"family": "Villanueva"},
            self.registry_slug,
        )
        self.assertItemsEqual([
            ("Jane", self.domain_1),
            ("Xiomara", self.domain_1),
            ("Alba", self.domain_1),
            ("Jane", self.domain_3),
        ], results)

    def test_subset_of_domains_accessible(self):
        # Domain 2 has access only to domains 1 and itself
        results = self._run_query(
            self.domain_2,
            ['person'],
            {"name": "Jane"},
            self.registry_slug,
        )
        self.assertItemsEqual([
            ("Jane", self.domain_1),
            ("Jane", self.domain_1),
            ("Jane", self.domain_2),
        ], results)

    def test_in_registry_but_no_grants(self):
        # Domain 3 has access only to its own cases
        results = self._run_query(
            self.domain_3,
            ['person'],
            {"name": "Jane"},
            self.registry_slug,
        )
        self.assertItemsEqual([
            ("Jane", self.domain_3),
        ], results)

    def test_invalid_registry_can_access_own_cases(self):
        results = self._run_query(
            self.domain_1,
            ['person'],
            {"name": "Jane"},
            "fake-registry",
        )
        self.assertItemsEqual([
            ("Jane", self.domain_1),
            ("Jane", self.domain_1),
        ], results)

    def test_case_type_not_in_registry(self):
        # "creator" case types aren't in the registry, so only return the current domain cases
        results = self._run_query(
            self.domain_1,
            ['creator'],
            {},
            self.registry_slug,
        )
        self.assertItemsEqual([
            ("Jennie Snyder Urman", self.domain_1),
        ], results)

    def test_access_related_case_type_not_in_registry(self):
        # "creative_work" case types are in the registry, but not their parents - "creator"
        # domain 1 can access a domain 2 case even while referencing an inaccessible case type property
        results = self._run_query(
            self.domain_1,
            ['creative_work'],
            {"parent/name": "Charlotte Brontë"},
            self.registry_slug,
        )
        self.assertItemsEqual([
            ("Jane Eyre", self.domain_2),
        ], results)

    def test_search_commcare_project(self):
        results = self._run_query(
            self.domain_1,
            ["person"],
            {"name": "Jane", COMMCARE_PROJECT: [self.domain_2, self.domain_3]},
            self.registry_slug,
        )
        self.assertItemsEqual([
            ("Jane", self.domain_2),
            ("Jane", self.domain_3),
        ], results)

    def test_commcare_project_field_doesnt_expand_access(self):
        # Domain 3 has access only to its own cases and can't get results from
        # domain 1, even by specifying it manually
        results = self._run_query(
            self.domain_3,
            ['person'],
            {"name": "Jane", COMMCARE_PROJECT: self.domain_1},
            self.registry_slug,
        )
        self.assertItemsEqual([], results)

    def test_includes_project_property(self):
        results = get_case_search_results(
            self.domain_1,
            ["person"],
            [SearchCriteria("name", "Jane")],
            registry_slug=self.registry_slug
        )
        self.assertItemsEqual([
            ("Jane", self.domain_1, self.domain_1),
            ("Jane", self.domain_1, self.domain_1),
            ("Jane", self.domain_2, self.domain_2),
            ("Jane", self.domain_3, self.domain_3),
        ], [
            (case.name, case.domain, case.get_case_property('commcare_project'))
            for case in results
        ])

    def test_related_cases_included(self):
        with patch_get_app_cached:
            results = get_case_search_results(
                self.domain_1,
                ["creative_work"],
                [SearchCriteria("name", "Jane Eyre")],  # from domain 2
                app_id="mock_app_id",
                registry_slug=self.registry_slug
            )
        self.assertItemsEqual([
            ("Charlotte Brontë", "creator", self.domain_2),
            ("Jane Eyre", "creative_work", self.domain_2),
        ], [
            (case.name, case.type, case.domain)
            for case in results
        ])

    def test_primary_cases_not_included_with_related_cases(self):
        with patch_get_app_cached:
            registry_helper = _get_helper(None, self.domain_1, ["creative_work"], self.registry_slug)
            primary_cases = get_primary_case_search_results(registry_helper, self.domain_1, ["creative_work"],
                                                            [SearchCriteria("name", "Jane Eyre")])
            related_cases = registry_helper.get_all_related_live_cases(primary_cases)

            self.assertItemsEqual([
                ("Charlotte Brontë", "creator", self.domain_2),
            ], [
                (case.name, case.type, case.domain)
                for case in related_cases
            ])

class TestCaseSearchRegistryPermissions(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.domain = 'registry-permissions'
        cls.user = create_user('admin', '123')

        cls.registry_slug = create_registry_for_test(
            cls.user,
            cls.domain,
            invitations=[Invitation("A"), Invitation("B")],
            grants=[
                Grant("A", [cls.domain]),
                Grant("B", [cls.domain]),
            ],
            name="reg1",
            case_types=["herb"]
        ).slug

    def test_user_without_permission_cannot_access_all_domains(self):
        domains = self._get_registry_visible_domains(HqPermissions(view_data_registry_contents=False))
        self.assertEqual(domains, {self.domain})

    def test_user_with_permission_can_access_all_domains(self):
        domains = self._get_registry_visible_domains(HqPermissions(view_data_registry_contents=True))
        self.assertEqual(domains, {self.domain, "A", "B"})

    def _get_registry_visible_domains(self, permissions):
        mock_role = mock.Mock(permissions=permissions)
        mock_user = mock.Mock(get_role=mock.Mock(return_value=mock_role))
        helper = _get_helper(
                mock_user,
                self.domain,
                ["herb"],
                self.registry_slug,
            )
        return set(helper.query_domains)
