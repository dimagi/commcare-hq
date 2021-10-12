import logging
from datetime import datetime
from unittest.mock import patch
from uuid import uuid4

from couchdbkit import ResourceNotFound
from django.conf import settings
from django.test import TestCase, TransactionTestCase
from django.utils.decorators import classproperty
from nose.plugins.attrib import attr
from nose.tools import nottest
from unittest import skipIf, skipUnless

from casexml.apps.case.models import CommCareCase
from casexml.apps.phone.models import SyncLogSQL
from corehq.blobs import CODES
from corehq.blobs.models import BlobMeta
from corehq.form_processor.backends.sql.dbaccessors import (
    CaseAccessorSQL, LedgerAccessorSQL, LedgerReindexAccessor,
    iter_all_rows, FormAccessorSQL)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import XFormInstanceSQL, CommCareCaseSQL, CaseTransaction, Attachment
from corehq.sql_db.models import PartitionedModel
from corehq.util.test_utils import unit_testing_only
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import safe_delete

from .json2xml import convert_form_to_xml

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
    @unit_testing_only
    def delete_all_ledgers(domain=None):
        logger.debug("Deleting all ledgers for domain %s", domain)

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
        cls._delete_all(XFormInstance.get_db(), XFormInstanceSQL.ALL_DOC_TYPES, domain)
        FormProcessorTestUtils.delete_all_sql_forms(domain)

    @classmethod
    @unit_testing_only
    def delete_all_sql_forms(cls, domain=None):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        logger.debug("Deleting all SQL xforms for domain %s", domain)
        params = {"type_code__in": [CODES.form_xml, CODES.form_attachment]}
        if domain:
            params["domain"] = domain
        for db in get_db_aliases_for_partitioned_query():
            BlobMeta.objects.using(db).filter(**params).delete()
        cls._delete_all_sql_sharded_models(XFormInstanceSQL, domain)

    @classmethod
    @unit_testing_only
    def delete_all_sync_logs(cls):
        SyncLogSQL.objects.all().delete()

    @staticmethod
    @unit_testing_only
    def _delete_all_sql_sharded_models(model_class, domain=None):
        assert issubclass(model_class, PartitionedModel)
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        dbs = get_db_aliases_for_partitioned_query()
        for db in dbs:
            query = model_class.objects.using(db)
            if domain:
                query = query.filter(domain=domain)
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


def sharded(cls):
    """Tag tests to run with the sharded SQL backend

    This adds a "sharded" attribute to decorated tests indicating that
    the tests should be run with a sharded database setup. Note that the
    presence of that attribute does not prevent tests from  also running
    in the default not-sharded database setup.

    Was previously named @use_sql_backend
    """
    return patch_shard_db_transactions(attr(sharded=True)(cls))


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
    return skip_unless(sharded(cls))


def patch_testcase_databases():
    """Lift Django 2.2 restriction on database access in tests

    Allows `TestCase` and `TransactionTestCase` to access all databases
    by default. ICDS-specific databases are only accessible in icds
    tests. This can be overridden by setting `databases` on test case
    subclasses.

    Similar to pre-Django 2.2, transactions are disabled on all
    databases except "default". This can be overridden by setting
    `transaction_exempt_databases` on test case subclasses.

    For test performance it may be better to remove this and tag each
    test with the databases it will query.
    """
    # According to the docs it should be possible to allow tests to
    # access all databases with `TestCase.databses = '_all__'`
    # https://docs.djangoproject.com/en/2.2/topics/testing/tools/#multi-database-support
    #
    # Unfortunately support for '__all__' appears to be buggy:
    # django.db.utils.ConnectionDoesNotExist: The connection _ doesn't exist
    #
    # Similar error reported elsewhere:
    # https://code.djangoproject.com/ticket/30541
    default_dbs = frozenset(k for k in settings.DATABASES.keys() if "icds" not in k)
    icds_dbs = frozenset(settings.DATABASES.keys())

    def is_icds(cls):
        # TODO remove when custom.icds packages have been moved to new repo
        return cls.__module__.startswith("icds")

    @classproperty
    def databases(cls):
        return icds_dbs if is_icds(cls) else default_dbs
    TestCase.databases = databases
    TransactionTestCase.databases = databases

    @classproperty
    def transaction_exempt_databases(cls):
        databases = icds_dbs if is_icds(cls) else default_dbs
        if cls.databases is databases:
            return frozenset(db for db in databases if db != "default")
        return frozenset(db for db in databases if db not in cls.databases)
    TransactionTestCase.transaction_exempt_databases = transaction_exempt_databases

    @classmethod
    def _databases_names(cls, include_mirrors=True):
        names = super_database_names(cls, include_mirrors=include_mirrors)
        exempt = cls.transaction_exempt_databases
        return [n for n in names if n not in exempt]
    super_database_names = TransactionTestCase._databases_names.__func__
    TransactionTestCase._databases_names = _databases_names

    def _should_check_constraints(self, connection):
        # Prevent intermittent error:
        # Traceback (most recent call last):
        #   File "django/test/testcases.py", line 274, in __call__
        #     self._post_teardown()
        #   File "django/test/testcases.py", line 1009, in _post_teardown
        #     self._fixture_teardown()
        #   File "django/test/testcases.py", line 1176, in _fixture_teardown
        #     if self._should_check_constraints(connections[db_name]):
        #   File "django/test/testcases.py", line 1184, in _should_check_constraints
        #     not connection.needs_rollback and connection.is_usable()
        #   File "django/db/backends/postgresql/base.py", line 252, in is_usable
        #     self.connection.cursor().execute("SELECT 1")
        # AttributeError: 'NoneType' object has no attribute 'cursor'
        return (connection.connection is not None
            and super_should_check_constraints(self, connection))
    super_should_check_constraints = TestCase._should_check_constraints
    TestCase._should_check_constraints = _should_check_constraints


def patch_shard_db_transactions(cls):
    """Patch shard db transaction management on test class

    Do not use a transaction per test on shard databases because proxy
    queries cannot see changes in uncommitted transactions in shard dbs.
    This means that changes to shard dbs will not be rolled back at the
    end of each test; test cleanup must be done manually.

    :param cls: A test class.
    """
    if not issubclass(cls, TransactionTestCase):
        return cls
    shard_dbs = {k for k, v in settings.DATABASES.items() if "PLPROXY" in v}
    if shard_dbs:
        # Reassign attribute to prevent leaking this change to other
        # classes that share the same class attribute.
        pre_exempt = cls.transaction_exempt_databases
        cls.transaction_exempt_databases = frozenset(pre_exempt) | shard_dbs
    return cls


@nottest
def create_form_for_test(
    domain,
    case_id=None,
    attachments=None,
    save=True,
    state=XFormInstanceSQL.NORMAL,
    received_on=None,
    user_id=None,
    edited_on=None,
    *,
    form_id=None,
    form_data=None,
    **kwargs,
):
    """
    Create the models directly so that these tests aren't dependent on any
    other apps. Not testing form processing here anyway.
    :param case_id: create case with ID if supplied
    :param attachments: additional attachments dict
    :param save: if False return the unsaved form
    :return: form object
    """
    from corehq.form_processor.utils import get_simple_form_xml

    form_id = form_id or uuid4().hex
    utcnow = received_on or datetime.utcnow()
    kwargs.setdefault('xmlns', 'http://openrosa.org/formdesigner/form-processor')

    if form_data is not None:
        form_xml = convert_form_to_xml(form_data)
        if user_id is None and form_data.get('meta'):
            user_id = form_data['meta'].get('userID', user_id)
    else:
        form_xml = get_simple_form_xml(form_id, case_id)
    if user_id is None:
        user_id = 'user1'

    form = XFormInstanceSQL(
        form_id=form_id,
        received_on=utcnow,
        user_id=user_id,
        domain=domain,
        state=state,
        edited_on=edited_on,
        **kwargs,
    )

    attachments = attachments or {}
    attachment_tuples = [
        Attachment(name=a[0], raw_content=a[1], content_type=a[1].content_type)
        for a in attachments.items()
    ]
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
        case.track_create(CaseTransaction.form_transaction(case, form, utcnow))
        cases = [case]

    if save:
        FormProcessorSQL.save_processed_models(ProcessedForms(form, None), cases)
        form = FormAccessorSQL.get_form(form.form_id)

    return form


def create_case(case) -> CommCareCaseSQL:
    form = XFormInstanceSQL(
        form_id=uuid4().hex,
        xmlns='http://commcarehq.org/formdesigner/form-processor',
        received_on=case.server_modified_on,
        user_id=case.owner_id,
        domain=case.domain,
    )
    transaction = CaseTransaction(
        type=CaseTransaction.TYPE_FORM,
        form_id=form.form_id,
        case=case,
        server_date=case.server_modified_on,
    )
    with patch.object(FormProcessorSQL, "publish_changes_to_kafka"):
        case.track_create(transaction)
        processed_forms = ProcessedForms(form, [])
        FormProcessorSQL.save_processed_models(processed_forms, [case])
    return CaseAccessorSQL.get_case(case.case_id)


def create_case_with_index(case, index) -> CommCareCaseSQL:
    case = create_case(case)
    index.case = case
    case.track_create(index)
    CaseAccessorSQL.save_case(case)
    return case


def delete_all_xforms_and_cases(domain):
    assert settings.UNIT_TESTING
    FormProcessorTestUtils.delete_all_xforms(domain)
    FormProcessorTestUtils.delete_all_cases(domain)
