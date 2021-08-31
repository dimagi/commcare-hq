import uuid

from django.test import TestCase

from casexml.apps.case.mock import CaseBlock

from corehq.apps.case_search.models import CaseSearchConfig
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


@es_test
@run_with_sql_backend
class TestCaseSearchRegistry(TestCase):

    # TODO convert to setUpClass
    def setUp(self):
        self.user = create_user("admin", "123")
        self.domain_1 = "jane-the-virgin"
        self.setup_domain(self.domain_1, [
            ("Jane", {"family": "Villanueva"}),
            ("Xiomara", {"family": "Villanueva"}),
            ("Alba", {"family": "Villanueva"}),
            ("Rogelio", {"family": "de la Vega"}),
            ("Jane", {"family": "Ramos"}),
        ])
        self.domain_2 = "jane-eyre"
        self.setup_domain(self.domain_2, [
            ("Jane", {"family": "Eyre"}),
            ("Sarah", {"family": "Reed"}),
            ("John", {"family": "Reed"}),
            ("Eliza", {"family": "Reed"}),
            ("Georgiana", {"family": "Reed"}),
        ])
        self.domain_3 = "janes-addiction"
        self.setup_domain(self.domain_3, [
            ("Perry", {"family": "Farrell"}),
            ("Dave", {"family": "Navarro"}),
            ("Stephen", {"family": "Perkins"}),
            ("Chris", {"family": "Chaney"}),
        ])

        create_registry_for_test(
            self.user,
            self.domain_1,
            invitations=[
                Invitation(self.domain_2),
                Invitation(self.domain_3),
            ],
            grants=[
                Grant(self.domain_1, [self.domain_2, self.domain_3]),
                Grant(self.domain_2, [self.domain_1]),
                Grant(self.domain_3, []),
            ],
            name="reg1",
        )

    def setup_domain(self, domain, cases):
        CaseSearchConfig.objects.create(pk=domain, enabled=True)
        case_search_es_setup(domain, [
            CaseBlock(
                case_id=str(uuid.uuid4()),
                case_type='person',
                case_name=name,
                create=True,
                update=properties,
            ) for name, properties in cases
        ])

    def tearDown(self):
        case_search_es_teardown()

    def test(self):
        print("running")
