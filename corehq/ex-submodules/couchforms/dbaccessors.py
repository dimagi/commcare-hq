from couchforms.models import XFormInstance, doc_types
from dimagi.utils.couch.database import iter_docs


def get_forms_by_id(form_ids):
    forms = iter_docs(XFormInstance.get_db(), form_ids)
    doctypes = doc_types()
    return [doctypes[form['doc_type']].wrap(form) for form in forms if form.get('doc_type') in doctypes]
