import os
import functools
import logging
from datetime import datetime
from uuid import uuid4

from couchdbkit import ResourceNotFound
from django.conf import settings
from nose.tools import nottest

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLog
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL, FormAccessorSQL, LedgerAccessorSQL, LedgerReindexAccessor
)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import FormProcessorInterface, ProcessedForms
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, CaseTransaction, Attachment
from corehq.form_processor.parsers.form import process_xform_xml
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.sql_db.config import get_sql_db_aliases_in_use
from corehq.util.test_utils import unit_testing_only, run_with_multiple_configs, RunConfig
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import safe_delete

logger = logging.getLogger(__name__)


class FormProcessorTestUtils(object):

    @classmethod
    @unit_testing_only
    def delete_all_cases_forms_ledgers(cls, domain=None):
        cls.delete_all_ledgers(domain)
        cls.delete_all_cases(domain)
        cls.delete_all_xforms(domain)

    @classmethod
    @unit_testing_only
    def delete_all_cases(cls, domain=None):
        logger.debug("Deleting all Couch cases for domain %s", domain)
        assert CommCareCase.get_db().dbname.startswith('test_')
        view_kwargs = {}
        if domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}],
            }

        cls._delete_all(
            CommCareCase.get_db(),
            'cases_by_server_date/by_server_modified_on',
            **view_kwargs
        )

        FormProcessorTestUtils.delete_all_sql_cases(domain)

    @staticmethod
    @unit_testing_only
    def delete_all_sql_cases(domain=None):
        logger.debug("Deleting all SQL cases for domain %s", domain)
        CaseAccessorSQL.delete_all_cases(domain)

    @staticmethod
    def delete_all_ledgers(domain=None):
        FormProcessorTestUtils.delete_all_v2_ledgers(domain)
        FormProcessorTestUtils.delete_all_v1_ledgers(domain)

    @staticmethod
    @unit_testing_only
    def delete_all_v1_ledgers(domain=None):
        logger.debug("Deleting all V1 ledgers for domain %s", domain)
        from casexml.apps.stock.models import StockReport
        from casexml.apps.stock.models import StockTransaction
        stock_report_ids = StockReport.objects.filter(domain=domain).values_list('id', flat=True)
        StockReport.objects.filter(domain=domain).delete()
        StockTransaction.objects.filter(report_id__in=stock_report_ids).delete()

    @staticmethod
    @unit_testing_only
    def delete_all_v2_ledgers(domain=None):
        logger.debug("Deleting all V2 ledgers for domain %s", domain)

        def _delete_ledgers_for_case(case_id):
            transactions = LedgerAccessorSQL.get_ledger_transactions_for_case(case_id)
            form_ids = {tx.form_id for tx in transactions}
            for form_id in form_ids:
                LedgerAccessorSQL.delete_ledger_transactions_for_form([case_id], form_id)
            LedgerAccessorSQL.delete_ledger_values(case_id)

        if not domain:
            for db in get_sql_db_aliases_in_use():
                for ledger in LedgerReindexAccessor().get_docs(db, None, limit=10000):
                    _delete_ledgers_for_case(ledger.case_id)
        else:
            for case_id in CaseAccessorSQL.get_case_ids_in_domain(domain):
                _delete_ledgers_for_case(case_id)

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls, domain=None, user_id=None):
        logger.debug("Deleting all Couch xforms for domain %s", domain)
        view = 'couchforms/all_submissions_by_domain'
        view_kwargs = {}
        if domain and user_id:
            view = 'all_forms/view'
            view_kwargs = {
                'startkey': ['submission user', domain, user_id],
                'endkey': ['submission user', domain, user_id, {}],

            }
        elif domain:
            view_kwargs = {
                'startkey': [domain],
                'endkey': [domain, {}]
            }

        cls._delete_all(
            XFormInstance.get_db(),
            view,
            **view_kwargs
        )

        FormProcessorTestUtils.delete_all_sql_forms(domain, user_id)

    @staticmethod
    @unit_testing_only
    def delete_all_sql_forms(domain=None, user_id=None):
        logger.debug("Deleting all SQL xforms for domain %s", domain)
        FormAccessorSQL.delete_all_forms(domain, user_id)

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        logger.debug("Deleting all synclogs")
        cls._delete_all(SyncLog.get_db(), 'phone/sync_logs_by_user')

    @staticmethod
    @unit_testing_only
    def _delete_all(db, viewname, **view_kwargs):
        deleted = set()
        for row in db.view(viewname, reduce=False, **view_kwargs):
            doc_id = row['id']
            if doc_id not in deleted:
                try:
                    safe_delete(db, doc_id)
                    deleted.add(doc_id)
                except ResourceNotFound:
                    pass


def _conditionally_run_with_all_backends():
    '''
    Conditionally runs both backends. By default will run both backends, if
    USE_SQL_BACKEND_ONLY=1, then it will only run the sql backend.

    This is particularly useful for travis. We want to be able to test
    both couch and sql on a single database. However, we also want to be
    able to test the sql backend on a sharded backend. It's redundant
    to run couch backend as well.
    '''

    should_run_sql_only = os.environ.get('USE_SQL_BACKEND_ONLY') == 'yes'

    def sql_pre_run(*args, **kwargs):
        # When running just SQL tests we need to tear down the couch setup and setup for sql
        with args[0].settings(TESTS_SHOULD_USE_SQL_BACKEND=False):
            args[0].tearDown()
        args[0].setUp()
    run_configs = [
        # run with default setting
        RunConfig(
            pre_run=sql_pre_run if should_run_sql_only else None,
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': should_run_sql_only,
            },
            post_run=lambda *args, **kwargs: args[0].tearDown() if not should_run_sql_only else None,
        ),
    ]

    if not should_run_sql_only:
        run_configs.append(
            # run with inverse of default setting
            RunConfig(
                settings={
                    'TESTS_SHOULD_USE_SQL_BACKEND': False,
                },
                pre_run=lambda *args, **kwargs: args[0].setUp(),
            ),
        )

    return functools.partial(
        run_with_multiple_configs,
        run_configs=run_configs,
        nose_tags={'all_backends': True}
    )


conditionally_run_with_all_backends = _conditionally_run_with_all_backends()


@unit_testing_only
def post_xform(instance_xml, attachments=None, domain='test-domain'):
    """
    create a new xform and releases the lock

    this is a testing entry point only and is not to be used in real code

    """
    result = process_xform_xml(domain, instance_xml, attachments=attachments)
    with result.get_locked_forms() as xforms:
        FormProcessorInterface(domain).save_processed_models(xforms)
        return xforms[0]


@nottest
def create_form_for_test(domain, case_id=None, attachments=None, save=True, state=XFormInstanceSQL.NORMAL):
    """
    Create the models directly so that these tests aren't dependent on any
    other apps. Not testing form processing here anyway.
    :param case_id: create case with ID if supplied
    :param attachments: additional attachments dict
    :param save: if False return the unsaved form
    :return: form object
    """
    from corehq.form_processor.utils import get_simple_form_xml

    form_id = uuid4().hex
    user_id = 'user1'
    utcnow = datetime.utcnow()

    form_xml = get_simple_form_xml(form_id, case_id)

    form = XFormInstanceSQL(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=domain,
        state=state
    )

    attachments = attachments or {}
    attachment_tuples = map(
        lambda a: Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type),
        attachments.items()
    )
    attachment_tuples.append(Attachment('form.xml', form_xml, 'text/xml'))

    FormProcessorSQL.store_attachments(form, attachment_tuples)

    cases = []
    if case_id:
        case = CommCareCaseSQL(
            case_id=case_id,
            domain=domain,
            type='',
            owner_id=user_id,
            opened_on=utcnow,
            modified_on=utcnow,
            modified_by=user_id,
            server_modified_on=utcnow,
        )
        case.track_create(CaseTransaction.form_transaction(case, form))
        cases = [case]

    if save:
        FormProcessorSQL.save_processed_models(ProcessedForms(form, None), cases)
    return form


@unit_testing_only
def set_case_property_directly(case, property_name, value):
    if should_use_sql_backend(case.domain):
        case.case_json[property_name] = value
    else:
        setattr(case, property_name, value)
