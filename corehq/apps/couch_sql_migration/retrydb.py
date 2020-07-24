import logging

from django.db import close_old_connections
from django.db.utils import DatabaseError, InterfaceError

from dimagi.utils.couch.database import retry_on_couch_error
from dimagi.utils.retry import retry_on

from corehq.form_processor.backends.couch.dbaccessors import (
    CaseAccessorCouch,
    FormAccessorCouch,
)
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL,
    FormAccessorSQL,
    LedgerAccessorSQL,
)

log = logging.getLogger(__name__)


def retry_on_sql_error(func):
    retry = retry_on(DatabaseError, InterfaceError, should_retry=_close_connections)
    return retry(func)


def _close_connections(err):
    """Close old db connections, then return true to retry"""
    log.warning("retry on %s: %s", type(err).__name__, err)
    close_old_connections()
    return True


@retry_on_couch_error
def couch_form_exists(form_id):
    return FormAccessorCouch.form_exists(form_id)


@retry_on_couch_error
def get_couch_case(case_id):
    return CaseAccessorCouch.get_case(case_id)


@retry_on_couch_error
def get_couch_cases(case_ids):
    return CaseAccessorCouch.get_cases(case_ids)


@retry_on_couch_error
def get_couch_form(form_id):
    return FormAccessorCouch.get_form(form_id)


@retry_on_couch_error
def get_couch_forms(form_ids):
    return FormAccessorCouch.get_forms(form_ids)


@retry_on_sql_error
def get_sql_case(case_id):
    return CaseAccessorSQL.get_case(case_id)


@retry_on_sql_error
def get_sql_cases(case_ids):
    return CaseAccessorSQL.get_cases(case_ids)


@retry_on_sql_error
def get_sql_form(form_id):
    return FormAccessorSQL.get_form(form_id)


@retry_on_sql_error
def get_sql_forms(form_ids, **kw):
    return FormAccessorSQL.get_forms(form_ids, **kw)


@retry_on_sql_error
def get_sql_ledger_value(*args):
    return LedgerAccessorSQL.get_ledger_value(*args)


@retry_on_sql_error
def get_sql_ledger_values(case_ids):
    return LedgerAccessorSQL.get_ledger_values_for_cases(case_ids)


@retry_on_sql_error
def sql_form_exists(form_id):
    return FormAccessorSQL.form_exists(form_id)
