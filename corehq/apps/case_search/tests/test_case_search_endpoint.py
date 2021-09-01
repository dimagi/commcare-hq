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
from corehq.form_processor.tests.utils import run_with_sql_backend

from ..utils import get_case_search_results


@es_test
@run_with_sql_backend
class TestCaseSearchEndpoint(TestCase):
    domain = "TestCaseSearchEndpoint"

    # TODO convert to setUpClass after it stabilizes
    def setUp(self):
        self.user = create_user("admin", "123")
        CaseSearchConfig.objects.create(domain=self.domain, enabled=True)
        case_search_es_setup(self.domain, [
            CaseBlock(
                case_id=str(uuid.uuid4()),
                case_type='person',
                case_name=name,
                create=True,
                update=properties,
            ) for name, properties in [
                ("Jane", {"family": "Villanueva"}),
                ("Xiomara", {"family": "Villanueva"}),
                ("Alba", {"family": "Villanueva"}),
                ("Rogelio", {"family": "de la Vega"}),
                ("Jane", {"family": "Ramos"}),
            ]
        ])

    def tearDown(self):
        case_search_es_teardown()

    def test_no_filter(self):
        res = get_case_search_results(self.domain, {'case_type': 'person'})
        self.assertItemsEqual(["Jane", "Xiomara", "Alba", "Rogelio", "Jane"], [
            case.name for case in res
        ])
