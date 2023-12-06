from corehq.apps.change_feed import data_sources, topics
from corehq.apps.change_feed.producer import producer
from corehq.form_processor.signals import sql_case_post_save
from pillowtop.feed.interface import ChangeMeta


def publish_form_saved(form):
    producer.send_change(topics.FORM_SQL, change_meta_from_sql_form(form))


def change_meta_from_sql_form(form):
    return ChangeMeta(
        document_id=form.form_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.FORM_SQL,
        document_type=form.doc_type,
        document_subtype=form.xmlns,
        domain=form.domain,
        is_deletion=form.is_deleted,
    )


def publish_form_deleted(domain, form_id):
    producer.send_change(topics.FORM_SQL, ChangeMeta(
        document_id=form_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.FORM_SQL,
        document_type='XFormInstance-Deleted',
        domain=domain,
        is_deletion=True,
    ))


def publish_case_saved(case, associated_form_id=None, send_post_save_signal=True):
    """
    Publish the change to kafka and run case post-save signals.
    """
    producer.send_change(topics.CASE_SQL, change_meta_from_sql_case(case, associated_form_id))
    if send_post_save_signal:
        sql_case_post_save.send(case.__class__, case=case)


def change_meta_from_sql_case(case, associated_form_id=None):
    return ChangeMeta(
        document_id=case.case_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.CASE_SQL,
        document_type='CommCareCase',
        document_subtype=case.type,
        domain=case.domain,
        is_deletion=case.is_deleted,
        associated_document_id=associated_form_id
    )


def publish_case_deleted(domain, case_id):
    producer.send_change(topics.CASE_SQL, ChangeMeta(
        document_id=case_id,
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.CASE_SQL,
        document_type='CommCareCase-Deleted',
        domain=domain,
        is_deletion=True,
    ))


def publish_ledger_v2_saved(ledger_value):
    producer.send_change(topics.LEDGER, change_meta_from_ledger_v2(
        ledger_value.ledger_reference, ledger_value.domain
    ))


def publish_ledger_v2_deleted(domain, case_id, section_id, entry_id):
    from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
    ref = UniqueLedgerReference(
        case_id=case_id, section_id=section_id, entry_id=entry_id
    )
    producer.send_change(topics.LEDGER, change_meta_from_ledger_v2(ref, domain, True))


def change_meta_from_ledger_v2(ledger_ref, domain, deleted=False):
    return ChangeMeta(
        document_id=ledger_ref.as_id(),
        data_source_type=data_sources.SOURCE_SQL,
        data_source_name=data_sources.LEDGER_V2,
        document_type=topics.LEDGER,
        domain=domain,
        is_deletion=deleted,
    )
