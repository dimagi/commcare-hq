import uuid
from abc import ABC, abstractmethod

from corehq.apps.es.case_search import case_search_adapter
from corehq.apps.es.client import manager
from corehq.pillows.case_search import CaseSearchReindexerFactory
from corehq.util.test_utils import create_and_save_a_case


class CaseDataTestMixin(ABC):

    @property
    @abstractmethod
    def case_type(self):
        raise NotImplementedError(
            "Subclasses must define a case_type property."
        )

    def make_case(self, domain, case_properties, index=None, case_type=None):
        case_properties = case_properties or {}
        case_id = case_properties.pop('_id')
        case_type = case_properties.pop('case_type', case_type or self.case_type)
        case_name = f'case-name-{uuid.uuid4().hex}'
        owner_id = case_properties.pop('owner_id', None)
        case = create_and_save_a_case(
            domain, case_id, case_name, case_properties, owner_id=owner_id, case_type=case_type, index=index
        )
        return case

    def bootstrap_cases_in_es_for_domain(self, domain, input_cases, case_type=None):
        for case in input_cases:
            index = case.pop('index', None)
            self.make_case(domain, case, index=index, case_type=case_type)
        CaseSearchReindexerFactory(domain=domain).build().reindex()
        manager.index_refresh(case_search_adapter.index_name)
