from collections import Counter

from corehq.apps import es
from corehq.apps.data_pipeline_audit.dbacessors import get_primary_db_form_counts, get_es_counts_by_doc_type, \
    get_primary_db_case_counts
from corehq.apps.data_pipeline_audit.utils import map_counter_doc_types


def get_doc_counts_for_domain(domain):
    """
    :param domain:
    :return: List of tuples: ``(doc_type, primary_db_count, es_count)``
    """
    primary_db_counts = map_counter_doc_types(_get_primary_db_counts(domain))
    es_counts = map_counter_doc_types(get_es_counts_by_doc_type(domain, (es.CaseES, es.FormES)))
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
    return db_counts
