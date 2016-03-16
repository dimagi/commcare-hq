import inspect
import re

from casexml.apps.case.models import CommCareCase
from corehq.pillows.case import CasePillow
from corehq.pillows.const import CASE_SEARCH_ALIAS
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_MAPPING, CASE_SEARCH_INDEX


class CaseSearchPillow(CasePillow):
    """
    Nested case properties indexer.
    """
    es_alias = CASE_SEARCH_ALIAS

    es_index = CASE_SEARCH_INDEX
    default_mapping = CASE_SEARCH_MAPPING()

    def change_transform(self, doc_dict):
        return {
            '_id': doc_dict.get('_id'),
            'doc_type': doc_dict.get('doc_type'),
            'domain': doc_dict.get('domain'),
            'case_properties': _get_case_properties(doc_dict),
        }


def _get_case_properties(doc_dict):
    base_case_properties = [
        {'key': 'name', 'value': doc_dict.get('name')},
        {'key': 'external_id', 'value': doc_dict.get('external_id')}
    ]
    dynamic_case_properties = [
        {'key': key, 'value': value}
        for key, value in doc_dict.iteritems()
        if _is_dynamic_case_property(key)
    ]

    return base_case_properties + dynamic_case_properties


def _is_dynamic_case_property(prop):
    """
    Finds whether {prop} is a dynamic property of CommCareCase. If so, it is likely a case property.
    """
    return not inspect.isdatadescriptor(getattr(CommCareCase, prop, None)) and re.search(r'^[a-zA-Z]', prop)
