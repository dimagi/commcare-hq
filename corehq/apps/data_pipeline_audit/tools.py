from __future__ import absolute_import
from __future__ import unicode_literals
from collections import Counter

from corehq.apps import es
from corehq.apps.data_pipeline_audit.dbacessors import get_primary_db_form_counts, get_es_counts_by_doc_type, \
    get_primary_db_case_counts, get_es_user_counts_by_doc_type
from corehq.apps.data_pipeline_audit.utils import map_counter_doc_types
from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_class
from corehq.apps.users.dbaccessors.all_commcare_users import get_mobile_user_count, get_web_user_count
from corehq.apps.users.models import CommCareUser


def get_doc_counts_for_domain(domain):
    """
    :param domain:
    :return: List of tuples: ``(doc_type, primary_db_count, es_count)``
    """
    primary_db_counts = map_counter_doc_types(_get_primary_db_counts(domain))
    es_counts = map_counter_doc_types(
        get_es_counts_by_doc_type(domain, (es.CaseES, es.FormES))
    )
    es_counts.update(get_es_user_counts_by_doc_type(domain))

    all_doc_types = set(primary_db_counts) | set(es_counts)

    output_rows = []
    for doc_type in sorted(all_doc_types, key=lambda d: d.lower()):
        output_rows.append((
            doc_type,
            primary_db_counts[doc_type],
            es_counts[doc_type]
        ))

    return output_rows


def _get_primary_db_counts(domain):
    db_counts = Counter()
    db_counts.update(get_primary_db_form_counts(domain))
    db_counts.update(get_primary_db_case_counts(domain))

    mobile_user_count = get_mobile_user_count(domain)
    db_counts.update({
        'WebUser': get_web_user_count(domain),
        'CommCareUser': mobile_user_count,
        'CommCareUser-Deleted': get_doc_count_in_domain_by_class(domain, CommCareUser) - mobile_user_count
    })
    return db_counts
