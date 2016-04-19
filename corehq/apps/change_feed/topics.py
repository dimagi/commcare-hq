from .document_types import CASE, FORM, DOMAIN, META

# this is redundant but helps avoid import warnings until nothing references these
CASE = CASE
FORM = FORM
DOMAIN = DOMAIN
META = META

# new models
CASE_SQL = 'case-sql'
FORM_SQL = 'form-sql'
SMS = 'sms'


ALL = (
    CASE, FORM, META, CASE_SQL, FORM_SQL, SMS
)


def get_topic(document_type_object):
    return document_type_object.primary_type
