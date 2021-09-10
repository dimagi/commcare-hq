import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.case_search.models import CaseSearchConfig
from corehq.apps.case_search.utils import RegistryCaseSearchCriteria
from corehq.apps.domain.shortcuts import create_user
from corehq.apps.es.tests.utils import (
    case_search_es_setup,
    case_search_es_teardown,
    es_test,
)
from corehq.apps.registry.tests.utils import (
    Grant,
    Invitation,
    create_registry_for_test,
)
from corehq.form_processor.tests.utils import run_with_sql_backend


def case(name, type_, properties):
    return CaseBlock(
        case_id=str(uuid.uuid4()),
        case_type=type_,
        case_name=name,
        create=True,
        update=properties,
    )


@es_test
@run_with_sql_backend
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
        ])
        cls.domain_2 = "jane-eyre"
        cls.setup_domain(cls.domain_2, [
            case("Jane", 'person', {"family": "Eyre"}),
            case("Sarah", 'person', {"family": "Reed"}),
            case("John", 'person', {"family": "Reed"}),
            case("Eliza", 'person', {"family": "Reed"}),
            case("Georgiana", 'person', {"family": "Reed"}),
        ])
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
        ).slug

    @classmethod
    def setup_domain(cls, domain, cases):
        CaseSearchConfig.objects.create(pk=domain, enabled=True)
        case_search_es_setup(domain, cases)

    @classmethod
    def tearDownClass(cls):
        case_search_es_teardown()
        super().tearDownClass()

    def test_query_all_domains_in_registry(self):
        # Domain 1 has access to all three domains
        results = RegistryCaseSearchCriteria(self.domain_1, ['person'], {
            "name": "Jane",
        }, self.registry_slug).search_es.values_list("name", "domain")
        self.assertItemsEqual([
            ("Jane", self.domain_1),
            ("Jane", self.domain_1),
            ("Jane", self.domain_2),
            ("Jane", self.domain_3),
        ], results)

    def test_case_property_query(self):
        results = RegistryCaseSearchCriteria(self.domain_1, ['person'], {
            "family": "Villanueva",
        }, self.registry_slug).search_es.values_list("name", "domain")
        self.assertItemsEqual([
            ("Jane", self.domain_1),
            ("Xiomara", self.domain_1),
            ("Alba", self.domain_1),
            ("Jane", self.domain_3),
        ], results)

    def test_subset_of_domains_accessible(self):
        # Domain 2 has access only to domains 1 and itself
        results = RegistryCaseSearchCriteria(self.domain_2, ['person'], {
            "name": "Jane",
        }, self.registry_slug).search_es.values_list("name", "domain")
        self.assertItemsEqual([
            ("Jane", self.domain_1),
            ("Jane", self.domain_1),
            ("Jane", self.domain_2),
        ], results)

    def test_in_registry_but_no_grants(self):
        # Domain 3 has access only to its own cases
        results = RegistryCaseSearchCriteria(self.domain_3, ['person'], {
            "name": "Jane",
        }, self.registry_slug).search_es.values_list("name", "domain")
        self.assertItemsEqual([
            ("Jane", self.domain_3),
        ], results)

    def test_case_type_not_in_registry(self):
        pass

    def test_includes_project_property(self):
        # TODO insert 'commcare_project'
        pass

    def test_related_cases_included(self):
        pass
