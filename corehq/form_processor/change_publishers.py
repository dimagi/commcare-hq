from __future__ import absolute_import
from __future__ import unicode_literals
from casexml.apps.case.xform import get_case_ids_from_form
from corehq.apps.change_feed import topics
from corehq.apps.change_feed.document_types import change_meta_from_doc
from corehq.apps.change_feed.producer import producer
from corehq.form_processor.interfaces.dbaccessors import FormAccessors, CaseAccessors
from corehq.form_processor.signals import sql_case_post_save
from pillowtop.feed.interface import ChangeMeta


def republish_all_changes_for_form(domain, form_id):
    """
    Publishes all changes for the form and any touched cases/ledgers.

    """
    form = FormAccessors(domain=domain).get_form(form_id)
    publish_form_saved(form)
    for case in get_cases_from_form(domain, form):
        publish_case_saved(case, send_post_save_signal=False)
    _publish_ledgers_from_form(domain, form)


def publish_form_saved(form):
    producer.send_change(topics.FORM_SQL, change_meta_from_doc(form.to_json()))


def publish_form_deleted(domain, form_id):
    producer.send_change(topics.FORM_SQL, ChangeMeta(
        document_id=form_id,
        data_source_type='sql',
        document_type='XFormInstance-Deleted',
        domain=domain,
        is_deletion=True,
    ))


def publish_case_saved(case, send_post_save_signal=True):
    """
    Publish the change to kafka and run case post-save signals.
    """
    producer.send_change(topics.CASE_SQL, change_meta_from_doc(case.to_json()))
    if send_post_save_signal:
        sql_case_post_save.send(case.__class__, case=case)


def publish_case_deleted(domain, case_id):
    producer.send_change(topics.CASE_SQL, ChangeMeta(
        document_id=case_id,
        data_source_type='sql',
        document_type='CommCareCase-Deleted',
        domain=domain,
        is_deletion=True,
    ))


def publish_ledger_v2_saved(ledger_value):
    producer.send_change(topics.LEDGER_V2, change_meta_from_ledger_v2(
        ledger_value.ledger_reference, ledger_value.domain
    ))


def publish_ledger_v2_deleted(domain, case_id, section_id, entry_id):
    from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
    ref = UniqueLedgerReference(
        case_id=case_id, section_id=section_id, entry_id=entry_id
    )
    producer.send_change(topics.LEDGER_V2, change_meta_from_ledger_v2(ref, domain, True))


def change_meta_from_ledger_v2(ledger_ref, domain, deleted=False):
    return ChangeMeta(
        document_id=ledger_ref.as_id(),
        document_type=topics.LEDGER_V2,
        domain=domain,
        is_deletion=deleted,
    )


def publish_ledger_v1_saved(stock_state, deleted=False):
    producer.send_change(topics.LEDGER, change_meta_from_ledger_v1(stock_state, deleted))


def change_meta_from_ledger_v1(stock_state, deleted=False):
    return ChangeMeta(
        document_id=stock_state.pk,
        document_type=topics.LEDGER,
        domain=stock_state.domain,
        is_deletion=deleted,
    )


def get_cases_from_form(domain, form):
    from corehq.form_processor.parsers.ledgers.form import get_case_ids_from_stock_transactions
    case_ids = get_case_ids_from_form(form) | get_case_ids_from_stock_transactions(form)
    return CaseAccessors(domain).get_cases(list(case_ids))


def _publish_ledgers_from_form(domain, form):
    from corehq.form_processor.parsers.ledgers.form import get_all_stock_report_helpers_from_form
    unique_references = {
        transaction.ledger_reference
        for helper in get_all_stock_report_helpers_from_form(form)
        for transaction in helper.transactions
    }

    topic = topics.LEDGER_V2 if form.to_json()['backend_id'] == 'sql' else topics.LEDGER
    for ledger_reference in unique_references:
        change_meta = _change_meta_from_ledger_reference(domain, ledger_reference, topic)
        producer.send_change(topic, change_meta)


def _change_meta_from_ledger_reference(domain, ledger_reference, topic):
    return ChangeMeta(
        document_id=ledger_reference.as_id(),
        document_type=topic,
        domain=domain,
        is_deletion=False,
    )
