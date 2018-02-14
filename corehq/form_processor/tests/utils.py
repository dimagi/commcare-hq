from __future__ import absolute_import
import functools
import logging
from datetime import datetime
from uuid import uuid4

from couchdbkit import ResourceNotFound
from django.conf import settings
from django.test.utils import override_settings
from nose.plugins.attrib import attr
from nose.tools import nottest
from unittest2 import skipIf, skipUnless

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLogSQL, SyncLog
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL, LedgerAccessorSQL, LedgerReindexAccessor,
    iter_all_rows)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, CaseTransaction, Attachment
from corehq.form_processor.utils.general import should_use_sql_backend
from corehq.sql_db.config import get_sql_db_aliases_in_use
from corehq.sql_db.models import PartitionedModel
from corehq.util.test_utils import unit_testing_only, run_with_multiple_configs, RunConfig
from couchforms.models import XFormInstance, all_known_formlike_doc_types
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
        cls._delete_all(CommCareCase.get_db(), ['CommCareCase', 'CommCareCase-Deleted'], domain)
        FormProcessorTestUtils.delete_all_sql_cases(domain)

    @classmethod
    @unit_testing_only
    def delete_all_sql_cases(cls, domain=None):
        logger.debug("Deleting all SQL cases for domain %s", domain)
        cls._delete_all_sql_sharded_models(CommCareCaseSQL, domain)

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
            for ledger in iter_all_rows(LedgerReindexAccessor()):
                _delete_ledgers_for_case(ledger.case_id)
        else:
            for case_id in CaseAccessorSQL.get_case_ids_in_domain(domain):
                _delete_ledgers_for_case(case_id)

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls, domain=None):
        logger.debug("Deleting all Couch xforms for domain %s", domain)
        cls._delete_all(XFormInstance.get_db(), all_known_formlike_doc_types(), domain)
        FormProcessorTestUtils.delete_all_sql_forms(domain)

    @classmethod
    @unit_testing_only
    def delete_all_sql_forms(cls, domain=None):
        logger.debug("Deleting all SQL xforms for domain %s", domain)
        cls._delete_all_sql_sharded_models(XFormInstanceSQL, domain)

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        SyncLogSQL.objects.all().delete()
        cls._delete_all_from_view(SyncLog.get_db(), 'phone/sync_logs_by_user')

    @staticmethod
    @unit_testing_only
    def _delete_all_sql_sharded_models(model_class, domain=None):
        assert issubclass(model_class, PartitionedModel)
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            query = model_class.objects.using(db)
            if domain:
                query.filter(domain=domain)
            query.delete()

    @staticmethod
    @unit_testing_only
    def _delete_all(db, doc_types, domain=None):
        for doc_type in doc_types:
            if domain:
                view = 'by_domain_doc_type_date/view'
                view_kwargs = {
                    'startkey': [domain, doc_type],
                    'endkey': [domain, doc_type, {}],
                }
            else:
                view = 'all_docs/by_doc_type'
                view_kwargs = {
                    'startkey': [doc_type],
                    'endkey': [doc_type, {}],
                }

            FormProcessorTestUtils._delete_all_from_view(db, view, view_kwargs)

    @staticmethod
    def _delete_all_from_view(db, view, view_kwargs=None):
        view_kwargs = view_kwargs or {}
        deleted = set()
        for row in db.view(view, reduce=False, **view_kwargs):
            doc_id = row['id']
            if doc_id not in deleted:
                try:
                    safe_delete(db, doc_id)
                    deleted.add(doc_id)
                except ResourceNotFound:
                    pass


run_with_all_backends = functools.partial(
    run_with_multiple_configs,
    run_configs=[
        # run with default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            post_run=lambda *args, **kwargs: args[0].tearDown()
        ),
        # run with inverse of default setting
        RunConfig(
            settings={
                'TESTS_SHOULD_USE_SQL_BACKEND': not getattr(settings, 'TESTS_SHOULD_USE_SQL_BACKEND', False),
            },
            pre_run=lambda *args, **kwargs: args[0].setUp(),
        ),
    ],
    nose_tags={'all_backends': True}
)


def partitioned(cls):
    """
    Marks a test to be run with the partitioned database settings in
    addition to the non-partitioned database settings.
    """
    return attr(sql_backend=True)(cls)


def only_run_with_non_partitioned_database(cls):
    """
    Only runs the test with the non-partitioned database settings.
    """
    skip_if = skipIf(
        settings.USE_PARTITIONED_DATABASE, 'Only applicable when sharding is not setup'
    )
    return skip_if(cls)


def only_run_with_partitioned_database(cls):
    """
    Only runs the test with the partitioned database settings.
    """
    skip_unless = skipUnless(
        settings.USE_PARTITIONED_DATABASE, 'Only applicable if sharding is setup'
    )
    return skip_unless(partitioned(cls))


def use_sql_backend(cls):
    return partitioned(override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)(cls))


@nottest
def create_form_for_test(
        domain, case_id=None, attachments=None, save=True, state=XFormInstanceSQL.NORMAL,
        received_on=None, user_id='user1', edited_on=None):
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
    utcnow = received_on or datetime.utcnow()

    form_xml = get_simple_form_xml(form_id, case_id)

    form = XFormInstanceSQL(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=utcnow,
        user_id=user_id,
        domain=domain,
        state=state,
        edited_on=edited_on,
    )

    attachments = attachments or {}
    attachment_tuples = [Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type) for a in attachments.items()]
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
