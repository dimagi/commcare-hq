from elasticsearch import ElasticsearchException

from corehq.apps.es import CaseES, GroupES, LedgerES
from corehq.apps.es import FormES
from corehq.apps.es.sms import SMSES
from corehq.apps.es.aggregations import AggregationTerm, NestedTermAggregationsHelper
from corehq.elastic import get_es_new, ES_EXPORT_INSTANCE
from corehq.toggles import EXPORT_NO_SORT


def get_form_export_base_query(domain, app_id, xmlns, include_errors):
    query = (FormES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .app(app_id)
            .xmlns(xmlns)
            .remove_default_filter('has_user'))

    if not EXPORT_NO_SORT.enabled(domain):
        query = query.sort("received_on")

    if include_errors:
        query = query.remove_default_filter("is_xform_instance")
        query = query.doc_type(["xforminstance", "xformarchived", "xformdeprecated", "xformduplicate"])
    return query


def get_case_export_base_query(domain, case_type):
    query = (CaseES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .case_type(case_type))

    if not EXPORT_NO_SORT.enabled(domain):
        query = query.sort("opened_on")

    return query


def get_sms_export_base_query(domain):
    return (SMSES(es_instance_alias=ES_EXPORT_INSTANCE)
            .domain(domain)
            .processed_or_incoming_messages()
            .sort("date"))


def get_groups_user_ids(group_ids):
    q = (GroupES()
         .doc_id(group_ids))

    results = []
    for user_list in q.values_list("users", flat=True):
        if isinstance(user_list, basestring):
            results.append(user_list)
        else:
            results.extend(user_list)

    return results


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
