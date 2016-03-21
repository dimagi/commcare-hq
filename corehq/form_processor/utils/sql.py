"""
Note that the adapters must return the fields in the same order as they appear
in the table DSL
"""
import json
from collections import namedtuple

from json_field.fields import JSONEncoder
from psycopg2.extensions import adapt, AsIs

from corehq.form_processor.models import (
    CommCareCaseSQL_DB_TABLE, CaseAttachmentSQL_DB_TABLE,
    CommCareCaseIndexSQL_DB_TABLE, CaseTransaction_DB_TABLE,
    XFormAttachmentSQL_DB_TABLE, XFormInstanceSQL_DB_TABLE,
    LedgerValue_DB_TABLE, LedgerTransaction_DB_TABLE)


def fetchall_as_namedtuple(cursor):
    "Return all rows from a cursor as a namedtuple"
    Result = _namedtuple_from_cursor(cursor)
    return [Result(*row) for row in cursor.fetchall()]


def fetchone_as_namedtuple(cursor):
    "Return one row from a cursor as a namedtuple"
    Result = _namedtuple_from_cursor(cursor)
    row = cursor.fetchone()
    return Result(*row)


def _namedtuple_from_cursor(cursor):
    desc = cursor.description
    return namedtuple('Result', [col[0] for col in desc])


def form_adapter(form):
    fields = [
        adapt(form.id).getquoted(),
        adapt(form.form_id).getquoted(),
        adapt(form.domain).getquoted(),
        adapt(form.app_id).getquoted(),
        adapt(form.xmlns).getquoted(),
        adapt(form.received_on).getquoted(),
        adapt(form.partial_submission).getquoted(),
        adapt(form.submit_ip).getquoted(),
        adapt(form.last_sync_token).getquoted(),
        adapt(form.date_header).getquoted(),
        adapt(form.build_id).getquoted(),
        adapt(form.state).getquoted(),
        adapt(json.dumps(form.auth_context, cls=JSONEncoder)).getquoted(),
        adapt(json.dumps(form.openrosa_headers, cls=JSONEncoder)).getquoted(),
        adapt(form.deprecated_form_id).getquoted(),
        adapt(form.edited_on).getquoted(),
        adapt(form.orig_id).getquoted(),
        adapt(form.problem).getquoted(),
        adapt(form.user_id).getquoted(),
        adapt(form.initial_processing_complete).getquoted(),
        adapt(form.deleted_on).getquoted(),
        adapt(form.deletion_id).getquoted(),
    ]
    return _adapt_fields(fields, XFormInstanceSQL_DB_TABLE)


def form_attachment_adapter(attachment):
    fields = [
        adapt(attachment.id).getquoted(),
        adapt(attachment.attachment_id).getquoted(),
        adapt(attachment.name).getquoted(),
        adapt(attachment.content_type).getquoted(),
        adapt(attachment.md5).getquoted(),
        adapt(attachment.form_id).getquoted(),
        adapt(attachment.blob_id).getquoted(),
        adapt(attachment.content_length).getquoted(),
        adapt(json.dumps(attachment.properties, cls=JSONEncoder)).getquoted(),
    ]
    return _adapt_fields(fields, XFormAttachmentSQL_DB_TABLE)


def case_adapter(case):
    fields = [
        adapt(case.id).getquoted(),
        adapt(case.case_id).getquoted(),
        adapt(case.domain).getquoted(),
        adapt(case.type).getquoted(),
        adapt(case.owner_id).getquoted(),
        adapt(case.opened_on).getquoted(),
        adapt(case.opened_by).getquoted(),
        adapt(case.modified_on).getquoted(),
        adapt(case.server_modified_on).getquoted(),
        adapt(case.modified_by).getquoted(),
        adapt(case.closed).getquoted(),
        adapt(case.closed_on).getquoted(),
        adapt(case.closed_by).getquoted(),
        adapt(case.deleted).getquoted(),
        adapt(case.external_id).getquoted(),
        adapt(json.dumps(case.case_json, cls=JSONEncoder)).getquoted(),
        adapt(case.name).getquoted(),
        adapt(case.location_id).getquoted(),
        adapt(case.deleted_on).getquoted(),
        adapt(case.deletion_id).getquoted(),
    ]
    return _adapt_fields(fields, CommCareCaseSQL_DB_TABLE)


def case_attachment_adapter(attachment):
    fields = [
        adapt(attachment.id).getquoted(),
        adapt(attachment.attachment_id).getquoted(),
        adapt(attachment.name).getquoted(),
        adapt(attachment.content_type).getquoted(),
        adapt(attachment.md5).getquoted(),
        adapt(attachment.case_id).getquoted(),
        adapt(attachment.blob_id).getquoted(),
        adapt(attachment.content_length).getquoted(),
        adapt(attachment.attachment_from).getquoted(),
        adapt(json.dumps(attachment.properties, cls=JSONEncoder)).getquoted(),
        adapt(attachment.attachment_src).getquoted(),
        adapt(attachment.identifier).getquoted(),
    ]
    return _adapt_fields(fields, CaseAttachmentSQL_DB_TABLE)


def case_index_adapter(index):
    fields = [
        adapt(index.id).getquoted(),
        adapt(index.domain).getquoted(),
        adapt(index.identifier).getquoted(),
        adapt(index.referenced_id).getquoted(),
        adapt(index.referenced_type).getquoted(),
        adapt(index.relationship_id).getquoted(),
        adapt(index.case_id).getquoted(),
    ]
    return _adapt_fields(fields, CommCareCaseIndexSQL_DB_TABLE)


def case_transaction_adapter(transaction):
    fields = [
        adapt(transaction.id).getquoted(),
        adapt(transaction.form_id).getquoted(),
        adapt(transaction.server_date).getquoted(),
        adapt(transaction.type).getquoted(),
        adapt(transaction.case_id).getquoted(),
        adapt(transaction.revoked).getquoted(),
        adapt(json.dumps(transaction.details, cls=JSONEncoder)).getquoted(),
        adapt(transaction.sync_log_id).getquoted(),
    ]
    return _adapt_fields(fields, CaseTransaction_DB_TABLE)


def ledger_value_adapter(ledger_value):
    fields = [
        adapt(ledger_value.id).getquoted(),
        adapt(ledger_value.entry_id).getquoted(),
        adapt(ledger_value.section_id).getquoted(),
        adapt(ledger_value.balance).getquoted(),
        adapt(ledger_value.last_modified).getquoted(),
        adapt(ledger_value.case_id).getquoted(),
    ]
    return _adapt_fields(fields, LedgerValue_DB_TABLE)


def ledger_transaction_adapter(ledger_transaction):
    fields = [
        adapt(ledger_transaction.id).getquoted(),
        adapt(ledger_transaction.form_id).getquoted(),
        adapt(ledger_transaction.server_date).getquoted(),
        adapt(ledger_transaction.report_date).getquoted(),
        adapt(ledger_transaction.type).getquoted(),
        adapt(ledger_transaction.case_id).getquoted(),
        adapt(ledger_transaction.entry_id).getquoted(),
        adapt(ledger_transaction.section_id).getquoted(),
        adapt(ledger_transaction.user_defined_type).getquoted(),
        adapt(ledger_transaction.delta).getquoted(),
        adapt(ledger_transaction.updated_balance).getquoted(),
    ]
    return _adapt_fields(fields, LedgerTransaction_DB_TABLE)


def _adapt_fields(fields, table_name):
    params = ['{}'] * len(fields)
    template = "ROW({})::{}".format(','.join(params), table_name)
    return AsIs(template.format(*fields))
