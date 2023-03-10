from corehq.util.es.elasticsearch import ElasticsearchException

from corehq.apps.es import CaseES, FormES, GroupES
from corehq.apps.es.sms import SMSES
from corehq.apps.es.cases import case_adapter


def get_form_export_base_query(domain, app_id, xmlns, include_errors):
    query = (FormES(for_export=True)
             .domain(domain)
             .xmlns(xmlns)
             .remove_default_filter('has_user'))

    if app_id:
        query = query.app(app_id)
    if include_errors:
        query = query.remove_default_filter("is_xform_instance")
        query = query.doc_type(["xforminstance", "xformarchived", "xformdeprecated", "xformduplicate"])
    return query.sort("received_on")


def get_case_export_base_query(domain, case_type):
    return (CaseES(for_export=True)
            .domain(domain)
            .case_type(case_type)
            .sort("opened_on")
            .sort('inserted_at', reset_sort=False))


def get_sms_export_base_query(domain):
    return (SMSES(for_export=True)
            .domain(domain)
            .processed_or_incoming_messages()
            .sort("date"))


def get_groups_user_ids(group_ids):
    q = (GroupES()
         .doc_id(group_ids))

    results = []
    for user_list in q.values_list("users", flat=True):
        if isinstance(user_list, str):
            results.append(user_list)
        else:
            results.extend(user_list)

    return results


def get_case_name(case_id):
    try:
        result = case_adapter.get(case_id, source_includes=['name'])
    except ElasticsearchException:
        return None

    return result['name']
