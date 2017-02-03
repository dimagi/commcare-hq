from elasticsearch import ElasticsearchException

from corehq.apps.es import CaseES, GroupES, LedgerES
from corehq.apps.es import FormES
from corehq.apps.es.aggregations import AggregationTerm, NestedTermAggregationsHelper
from corehq.elastic import get_es_new


def get_form_export_base_query(domain, app_id, xmlns, include_errors):
    query = (FormES()
            .domain(domain)
            .app(app_id)
            .xmlns(xmlns)
            .sort("received_on")
            .remove_default_filter('has_user'))
    if include_errors:
        query = query.remove_default_filter("is_xform_instance")
        query = query.doc_type(["xforminstance", "xformarchived", "xformdeprecated", "xformduplicate"])
    return query


def get_case_export_base_query(domain, case_type):
    return (CaseES()
            .domain(domain)
            .case_type(case_type)
            .sort("opened_on"))


def get_groups_user_ids(group_ids):
    q = (GroupES()
         .doc_id(group_ids))
    return [user for user_list in q.values_list("users", flat=True) for user in user_list]


def get_ledger_section_entry_combinations(domain):
    """Get all section / entry combinations in a domain.
    :returns: a generator of namedtuples with fields ``section_id``, ``entry_id``, ``doc_count``
    """
    terms = [
        AggregationTerm('section_id', 'section_id'),
        AggregationTerm('entry_id', 'entry_id'),
    ]
    query = LedgerES().domain(domain)
    return NestedTermAggregationsHelper(base_query=query, terms=terms).get_data()


def get_case_name(case_id):
    from corehq.pillows.mappings.case_mapping import CASE_INDEX_INFO
    try:
        result = get_es_new().get(CASE_INDEX_INFO.index, case_id, _source_include=['name'])
    except ElasticsearchException:
        return None

    return result['_source']['name']
