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
LEDGER = 'ledger'
COMMCARE_USER = 'commcare-user'
GROUP = 'group'
WEB_USER = 'web-user'


ALL = (
    CASE,
    CASE_SQL,
    COMMCARE_USER,
    DOMAIN,
    FORM,
    FORM_SQL,
    GROUP,
    LEDGER,
    META,
    SMS,
    WEB_USER,
)


def get_topic(document_type_object):
    return document_type_object.primary_type
