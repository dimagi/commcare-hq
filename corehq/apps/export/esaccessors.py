from corehq.apps.es import CaseES, GroupES
from corehq.apps.es import FormES


def get_form_export_base_query(domain, app_id, xmlns, include_errors):
    query = (FormES()
            .domain(domain)
            .app(app_id)
            .xmlns(xmlns)
            .sort("received_on"))
    if include_errors:
        query = query.remove_default_filter("is_xform_instance")
        # Assuming that the only other things in the FormES index are form errors,
        # but perhaps I should filter on those types explicitly.
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
