from corehq.apps.es import CaseES, GroupES, LedgerES
from corehq.apps.es import FormES
from corehq.apps.es.aggregations import AggregationTerm, NestedTermAggregationsHelper


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


def get_group_user_ids(group_id):
    q = (GroupES()
            .doc_id(group_id)
            .fields("users"))
    return q.run().hits[0]['users']


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


def get_case_name(case_id, domain):
    return (CaseES()
            .domain(domain)
            .case_ids([case_id])
            .values('name'))
