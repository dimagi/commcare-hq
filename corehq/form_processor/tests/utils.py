import logging
from contextlib import nullcontext
from datetime import datetime
from uuid import uuid4
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, TransactionTestCase
from django.utils.functional import classproperty

from nose.plugins.attrib import attr
from nose.tools import nottest
from unittest import skipIf, skipUnless

from casexml.apps.phone.models import SyncLogSQL
from corehq.blobs import CODES
from corehq.blobs.models import BlobMeta
from corehq.form_processor.backends.sql.dbaccessors import (
    LedgerAccessorSQL, LedgerReindexAccessor, iter_all_rows)
from corehq.form_processor.backends.sql.processor import FormProcessorSQL
from corehq.form_processor.interfaces.processor import ProcessedForms
from corehq.form_processor.models import (
    Attachment,
    CaseTransaction,
    CommCareCase,
    CommCareCaseIndex,
    XFormInstance,
)
from corehq.sql_db.models import PartitionedModel
from corehq.util.test_utils import unit_testing_only

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
        logger.debug("Deleting all SQL cases for domain %s", domain)
        cls._delete_all_sql_sharded_models(CommCareCase, domain)

    delete_all_sql_cases = delete_all_cases

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
            for case_id in CommCareCase.objects.get_case_ids_in_domain(domain):
                _delete_ledgers_for_case(case_id)

    @classmethod
    @unit_testing_only
    def delete_all_xforms(cls, domain=None):
        from corehq.sql_db.util import get_db_aliases_for_partitioned_query
        logger.debug("Deleting all SQL xforms for domain %s", domain)
        params = {"type_code__in": [CODES.form_xml, CODES.form_attachment]}
        if domain:
            params["domain"] = domain
        for db in get_db_aliases_for_partitioned_query():
            BlobMeta.objects.using(db).filter(**params).delete()
        cls._delete_all_sql_sharded_models(XFormInstance, domain)

    delete_all_sql_forms = delete_all_xforms

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
    by default. This can be overridden by setting `databases` on test
    case subclasses.

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
    default_dbs = frozenset(settings.DATABASES)

    TestCase.databases = default_dbs
    TransactionTestCase.databases = default_dbs

    @classproperty
    def transaction_exempt_databases(cls):
        if cls.databases is default_dbs:
            return frozenset(db for db in default_dbs if db != "default")
        return frozenset(db for db in default_dbs if db not in cls.databases)
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
    state=XFormInstance.NORMAL,
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

    form = XFormInstance(
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
        case = CommCareCase(
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
        form = XFormInstance.objects.get_form(form.form_id)

    return form


def create_case(
    domain,
    *,
    form_id=None,
    case_id=None,
    case_type='',
    user_id='user1',
    save=False,
    enable_kafka=False,
    **case_args,
):
    """Create case and related models directly (not via form processor)

    :param save: Save case if true. The default is false.
    :return: CommCareCase
    """
    form_id = form_id or uuid4().hex
    case_id = case_id or uuid4().hex
    utcnow = datetime.utcnow()
    case_args.setdefault("owner_id", user_id)
    case_args.setdefault("opened_on", utcnow)
    case_args.setdefault("modified_on", utcnow)
    case_args.setdefault("modified_by", user_id)
    received_on = case_args.setdefault("server_modified_on", utcnow)
    form = XFormInstance(
        form_id=form_id,
        xmlns='http://openrosa.org/formdesigner/form-processor',
        received_on=received_on,
        user_id=user_id,
        domain=domain
    )
    case = CommCareCase(
        case_id=case_id,
        domain=domain,
        type=case_type,
        **case_args
    )
    case.track_create(CaseTransaction.form_transaction(case, form, utcnow))
    if save:
        # disable publish to Kafka to avoid intermittent errors caused by
        # the nexus of kafka's consumer thread and freeze_time
        kafka_patch = patch.object(FormProcessorSQL, "publish_changes_to_kafka")
        with (nullcontext() if enable_kafka else kafka_patch):
            FormProcessorSQL.save_processed_models(ProcessedForms(form, None), [case])
    return case


def create_case_with_index(
    domain,
    referenced_case_id,
    identifier='parent',
    referenced_type='mother',
    relationship_id=CommCareCaseIndex.CHILD,
    case_is_deleted=False,
    case_type='child',
    *,
    save=False,
):
    case = create_case(domain, case_type=case_type)
    case.deleted = case_is_deleted
    index = CommCareCaseIndex(
        case=case,
        identifier=identifier,
        referenced_type=referenced_type,
        referenced_id=referenced_case_id,
        relationship_id=relationship_id
    )
    case.track_create(index)
    if save:
        case.save(with_tracked_models=True)
    return case, index


def delete_all_xforms_and_cases(domain):
    assert settings.UNIT_TESTING
    FormProcessorTestUtils.delete_all_xforms(domain)
    FormProcessorTestUtils.delete_all_cases(domain)
