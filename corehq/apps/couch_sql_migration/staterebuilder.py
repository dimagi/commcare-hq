import logging

from django.db import connections

from couchforms.models import XFormInstance
from dimagi.utils.couch.database import iter_docs

from corehq.apps.domain.dbaccessors import get_doc_count_in_domain_by_type
from corehq.form_processor.models import XFormInstanceSQL
from corehq.sql_db.util import split_list_by_db_partition
from corehq.util.couch_helpers import NoSkipArgsProvider
from corehq.util.log import with_progress_bar
from corehq.util.pagination import ResumableFunctionIterator

log = logging.getLogger(__name__)


def iter_unmigrated_docs(domain, doc_types, migration_id):
    if doc_types != ["XFormInstance"]:
        raise NotImplementedError(doc_types)
    [doc_type] = doc_types
    couch_db = XFormInstance.get_db()
    doc_count = get_doc_count_in_domain_by_type(domain, doc_type, couch_db)
    batches = doc_count // iter_id_chunks.chunk_size
    iterable = iter_id_chunks(domain, doc_type, migration_id, couch_db)
    doc_ids = []
    for doc_ids in with_progress_bar(iterable, batches, prefix=doc_type, oneline=False):
        yield from iter_docs_not_in_sql(doc_ids, couch_db)


def iter_id_chunks(domain, doc_type, migration_id, couch_db):
    def data_function(**view_kwargs):
        return couch_db.view('by_domain_doc_type_date/view', **view_kwargs)
    endkey, docid = get_endkey_docid(domain, doc_type, migration_id)
    args_provider = NoSkipArgsProvider({
        'startkey': [domain, doc_type],
        'endkey': endkey,
        'endkey_docid': docid,
        'inclusive_end': False,
        'limit': iter_id_chunks.chunk_size,
        'include_docs': False,
        'reduce': False,
    })
    args, kwargs = args_provider.get_initial_args()
    while True:
        results = list(data_function(*args, **kwargs))
        results = args_provider.adjust_results(results, args, kwargs)
        if not results:
            break
        yield [r["id"] for r in results]
        try:
            args, kwargs = args_provider.get_next_args(results[-1], *args, **kwargs)
        except StopIteration:
            break


iter_id_chunks.chunk_size = 1000


def get_endkey_docid(domain, doc_type, migration_id):
    resume_key = "%s.%s.%s" % (domain, doc_type, migration_id)
    state = ResumableFunctionIterator(resume_key, None, None, None).state
    assert getattr(state, '_rev', None), "rebuild not necessary (no resume state)"
    assert not state.complete, "iteration is complete"
    state_json = state.to_json()
    assert not state_json['args']
    kwargs = state_json['kwargs']
    return kwargs['startkey'], kwargs['startkey_docid']


def iter_docs_not_in_sql(form_ids, couch_db):
    def get_missing_form_ids(db, db_form_ids):
        with db.cursor() as cursor:
            cursor.execute(sql, [db_form_ids])
            return [r[0] for r in cursor.fetchall()]

    sql = f"""
        SELECT id FROM (
            (
                SELECT UNNEST(%s) AS id
            ) EXCEPT (
                SELECT form_id FROM {XFormInstanceSQL._meta.db_table}
            )
        ) AS missing_ids
    """

    for db_name, db_form_ids in split_list_by_db_partition(form_ids):
        missing_ids = get_missing_form_ids(connections[db_name], db_form_ids)
        if missing_ids:
            log.debug("missing ids: %s", missing_ids)
            yield from iter_docs(couch_db, missing_ids)
