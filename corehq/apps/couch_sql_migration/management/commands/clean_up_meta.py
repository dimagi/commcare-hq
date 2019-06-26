from couchforms.models import doc_types
from corehq.form_processor.backends.sql.dbaccessors import FormAccessorSQL
from corehq.blobs import get_blob_db, CODES, NotFound


def iter_sql_form_ids(domain):
    for doc_type in doc_types():
        for form_id in FormAccessorSQL.get_form_ids_in_domain_by_type(domain, doc_type):
            yield form_id


def delete_extra_meta(domain):
    blob_db = get_blob_db()
    for form_id in iter_sql_form_ids(domain):
        for meta in blob_db.metadb.get_for_parent(parent_id=form_id, type_code=CODES.form_xml):
            if meta.domain == domain:
                try:
                    form_xml = blob_db.get(meta.key)
                except NotFound:
                    meta.delete()
                else:
                    form_xml.close()
