import json
from collections import namedtuple
from psycopg2.extensions import adapt, register_adapter, AsIs


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
        adapt(json.dumps(form.auth_context)).getquoted(),
        adapt(json.dumps(form.openrosa_headers)).getquoted(),
        adapt(form.deprecated_form_id).getquoted(),
        adapt(form.edited_on).getquoted(),
        adapt(form.orig_id).getquoted(),
        adapt(form.problem).getquoted(),
        adapt(form.user_id).getquoted(),
        adapt(form.initial_processing_complete).getquoted(),
    ]
    return _adapt_fields(fields, 'form_processor_xforminstancesql')


def formattachment_adapter(attachment):
    fields = [
        adapt(attachment.id).getquoted(),
        adapt(attachment.attachment_id).getquoted(),
        adapt(attachment.name).getquoted(),
        adapt(attachment.content_type).getquoted(),
        adapt(attachment.md5).getquoted(),
        adapt(attachment.form_id).getquoted(),
    ]
    return _adapt_fields(fields, 'form_processor_xformattachmentsql')


def _adapt_fields(fields, table_name):
    params = ['{}'] * len(fields)
    template = "ROW({})::{}".format(','.join(params), table_name)
    return AsIs(template.format(*fields))
