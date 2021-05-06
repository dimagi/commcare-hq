from uuid import uuid4

from django.db import router
from django.test import TestCase
from django.utils.decorators import classproperty

from couchdbkit.ext.django.loading import get_db

from ..models import AuditEvent


class AuditcareTest(TestCase):

    @classproperty
    def databases(self):
        return {"default", router.db_for_read(AuditEvent)}


def save_couch_doc(doc_type, user, **doc):
    db = get_db("auditcare")
    doc.update(doc_type=doc_type, user=user, _id=uuid4().hex, base_type="AuditEvent")
    return db.save_doc(doc)["id"]


def delete_couch_docs(couch_ids):
    db = get_db("auditcare")
    for doc_id in couch_ids:
        db.delete_doc(doc_id)
