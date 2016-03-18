import inspect
import re

from casexml.apps.case.models import CommCareCase
from corehq.apps.es import DomainES
from corehq.pillows.case import CasePillow
from corehq.pillows.const import CASE_SEARCH_ALIAS
from corehq.pillows.mappings.case_search_mapping import CASE_SEARCH_INDEX, \
    CASE_SEARCH_MAPPING
from pillowtop.reindexer.change_providers.couch import CouchViewChangeProvider
from pillowtop.reindexer.reindexer import PillowReindexer


class CaseSearchPillow(CasePillow):
    """
    Nested case properties indexer.
    """
    es_alias = CASE_SEARCH_ALIAS

    es_index = CASE_SEARCH_INDEX
    default_mapping = CASE_SEARCH_MAPPING

    # TODO: Do this so that it isn't dependent on ES, because otherwise a full
    # reindex of this is dependent on having the DomainES index already
    # available. (i.e. running `ptop_fast_reindex` fails)
    # 1) Make an SQL table
    # 2) Just use the Toggle

    enabled_domains = [enabled_domain.get('name')
                       for enabled_domain
                       in DomainES().term('case_search_enabled', True).values()]

    def change_trigger(self, changes_dict):
        if self._is_new_style(changes_dict):
            domain = changes_dict.get('key')[0]
        else:
            domain = changes_dict.get('doc', {}).get('domain')

        if domain not in self.enabled_domains:
            return None

        return super(CaseSearchPillow, self).change_trigger(changes_dict)

    def _is_new_style(self, changes_dict):
        return (
            hasattr(changes_dict, 'id') and
            hasattr(changes_dict, 'value') and
            hasattr(changes_dict, 'key') and
            len(changes_dict) == 3
        )

    def change_transform(self, doc_dict):
        return transform_case_for_elasticsearch(doc_dict)


def transform_case_for_elasticsearch(doc_dict):
    doc = {
        desired_property: doc_dict.get(desired_property)
        for desired_property in CASE_SEARCH_MAPPING['properties'].keys()
        if desired_property != 'case_properties'
    }
    doc['_id'] = doc_dict.get('_id')
    doc['case_properties'] = _get_case_properties(doc_dict)
    return doc


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


def get_couch_case_search_reindexer(domain=None):
    # TODO: Figure out how to not fetch every single case from the DB when running a full reindex

    if domain is not None:
        startkey = [domain]
        endkey = [domain, {}, {}]
    else:
        startkey = []
        endkey = [{}, {}, {}]

    return PillowReindexer(CaseSearchPillow(), CouchViewChangeProvider(
        document_class=CommCareCase,
        view_name='cases_by_owner/view',
        view_kwargs={startkey: startkey, endkey: endkey}
    ))
