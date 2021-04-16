import datetime

from couchforms.models import XFormInstance

from dimagi.utils.chunked import chunked
from dimagi.utils.parsing import json_format_datetime

from corehq.toggles import ACTIVE_COUCH_DOMAINS
from corehq.util.metrics import metrics_gauge
from corehq.apps.es import FormES
from corehq.elastic import ES_EXPORT_INSTANCE
from corehq.pillows.xform import get_xform_pillow
from corehq.util.couch import bulk_get_revs
from corehq.apps.hqcase.management.commands.backfill_couch_forms_and_cases import (
    create_form_change_meta,
)


def cleanup_stale_es_on_couch_domains(
    start_date=None, end_date=None, domains=None, stdout=None
):
    """
    This is the response to https://dimagi-dev.atlassian.net/browse/SAAS-11489
    and basically makes sure that there are no stale docs in the most active
    domains still using the couch db backend until we can get them migrated.
    """
    end = end_date or datetime.datetime.utcnow()
    start = start_date or (end - datetime.timedelta(days=2))

    couch_domains = domains or ACTIVE_COUCH_DOMAINS.get_enabled_domains()

    for domain in couch_domains:
        form_ids, has_discrepancies = _get_all_form_ids(domain, start, end)
        if stdout:
            stdout.write(f"Found {len(form_ids)} in {domain} for between "
                         f"{start.isoformat()} and {end.isoformat()}.")
        if has_discrepancies:
            metrics_gauge(
                'commcare.es.couch_domain.couch_discrepancy_detected',
                1,
                tags={
                    'domain': domain,
                }
            )
            if stdout:
                stdout.write(f"\tFound discrepancies in form counts for domain {domain}")
        forms_not_in_es = _get_forms_not_in_es(form_ids)
        if forms_not_in_es:
            metrics_gauge(
                'commcare.es.couch_domain.stale_docs_in_es',
                len(forms_not_in_es),
                tags={
                    'domain': domain,
                }
            )
            if stdout:
                stdout.write(f"\tFound {len(forms_not_in_es)} forms not in es "
                             f"for {domain}")
            changes = _get_changes(domain, forms_not_in_es)
            form_es_processor = get_xform_pillow().processors[0]
            for change in changes:
                form_es_processor.process_change(change)


def _get_couch_form_ids(domain, start, end):
    """Get form IDs from the 'by_domain_doc_type_date/view' couch view"""
    form_ids = set()
    for doc_type in ['XFormArchived', 'XFormInstance']:
        startkey = [domain, doc_type, json_format_datetime(start)]
        endkey = [domain, doc_type, json_format_datetime(end)]
        results = XFormInstance.get_db().view(
            'by_domain_doc_type_date/view', startkey=startkey, endkey=endkey,
            reduce=False, include_docs=False
        )
        form_ids.update({row['id'] for row in results})
    return form_ids


def _get_all_form_ids(domain, start, end):
    """Get form IDs from couch multiple times to ensure we get them all
    This should not be necessary but for some reason we are seeing partial results.
    Also returns a boolean in the second parameter to indicate if there were
    any discrepancies in the results.
    """
    all_form_ids = None
    previous_form_ids = None
    form_id_differences = []
    for i in range(20):
        form_ids = _get_couch_form_ids(domain, start, end)
        if not all_form_ids:
            all_form_ids = form_ids
        else:
            form_id_differences.append(previous_form_ids.difference(form_ids))
            all_form_ids |= form_ids
        previous_form_ids = form_ids
    diff_counts = [len(diff) for diff in form_id_differences]
    return all_form_ids, any(diff_counts)


def _get_forms_in_es(form_ids):
    return (
        FormES(
            es_instance_alias=ES_EXPORT_INSTANCE
        ).remove_default_filters().form_ids(form_ids).values_list('_id', flat=True)
    )


def _get_forms_not_in_es(form_ids):
    not_in_es = []
    for chunk in chunked(list(form_ids), 1000):
        in_es = _get_forms_in_es(chunk)
        missing = set(chunk) - set(in_es)
        not_in_es.extend(missing)
    return not_in_es


def _change_from_meta(change_meta):
    from corehq.apps.change_feed.data_sources import get_document_store
    from pillowtop.feed.interface import Change

    document_store = get_document_store(
        data_source_type=change_meta.data_source_type,
        data_source_name=change_meta.data_source_name,
        domain=change_meta.domain,
        load_source="change_feed",
    )
    return Change(
        id=change_meta.document_id,
        sequence_id=None,
        document=None,
        deleted=change_meta.is_deletion,
        metadata=change_meta,
        document_store=document_store,
        topic=None,
        partition=None,
    )


def _get_changes(domain, doc_ids):
    c = []
    for ids in chunked(doc_ids, 500):
        doc_id_rev_list = {r[0]: r[1] for r in
                           bulk_get_revs(XFormInstance.get_db(), ids)}
        changes = [
            _change_from_meta(
                create_form_change_meta(domain, doc_id, doc_id_rev_list[doc_id])
            )
            for doc_id in ids
        ]
        c.extend(changes)
    return c
