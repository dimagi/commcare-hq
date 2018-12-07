from __future__ import absolute_import
from __future__ import unicode_literals

import json
import uuid

from couchdbkit.exceptions import ResourceConflict
from django.db import connection


def sql_save_with_resource_conflict(model, document, old_doc_rev=None):
    """Imitates the behavior of a couch save.

    If you are also saving to couch, this save should come after the couch
    save and the document's previous revision should be passed in.

    If you are not saving this same model to couch, do not pass in old_doc_rev
    """

    sql_only_model = old_doc_rev is None

    doc_id = document._id
    if sql_only_model:
        # this hasn't been saved to couch, so the document has the old revision
        old_doc_rev = document._rev
        new_doc_rev = uuid.uuid4().hex
    else:
        new_doc_rev = document._rev

    doc_json = document.to_json()
    doc_json['_rev'] = new_doc_rev
    doc_json_string = json.dumps(doc_json)

    with connection.cursor() as cursor:
        cursor.execute("""
        INSERT INTO {tablename} (
           id, rev, document
        ) VALUES (
           %(doc_id)s, %(new_doc_rev)s, %(doc_json)s
        )
        ON CONFLICT (id)
        DO UPDATE SET
           rev = %(new_doc_rev)s,
           document = %(doc_json)s
        WHERE {tablename}.rev = %(old_doc_rev)s
        RETURNING 1
        """.format(tablename=model._meta.db_table), {
            'doc_id': doc_id,
            'new_doc_rev': new_doc_rev,
            'doc_json': doc_json_string,
            'old_doc_rev': old_doc_rev
        })
        res = cursor.fetchone()

    if res is None:
        raise ResourceConflict(doc_id)

    if sql_only_model:
        # update the document in place. If couchdbkit is still handling saves,
        # it will do this for us
        document._rev = document._doc['_rev'] = new_doc_rev
