from couchforms.models import all_known_formlike_doc_types


CASE = 'case'
FORM = 'form'
META = 'meta'

# new models
CASE_SQL = 'case-sql'
FORM_SQL = 'form-sql'
SMS = 'sms'


ALL = (
    CASE, FORM, META, CASE_SQL, FORM_SQL, SMS
)


def get_topic(document_type):
    if document_type in ('CommCareCase', 'CommCareCase-Deleted'):
        return CASE
    elif document_type in all_known_formlike_doc_types():
        return FORM
    else:
        # at some point we may want to make this more granular
        return META
