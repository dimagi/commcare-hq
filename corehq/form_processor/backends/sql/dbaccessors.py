import functools
import itertools
import operator
import struct
from abc import ABCMeta, abstractmethod, abstractproperty
from collections import namedtuple
from uuid import UUID

from django.conf import settings
from django.db import InternalError, transaction, router
from django.db.models import Q
from django.db.models.expressions import Value
from django.db.models.functions import Concat

import csiphash

from dimagi.utils.chunked import chunked

from corehq.form_processor.exceptions import (
    CaseNotFound,
    LedgerSaveError,
    LedgerValueNotFound,
    MissingFormXml,
    XFormNotFound,
)
from corehq.form_processor.interfaces.dbaccessors import AbstractLedgerAccessor
from corehq.form_processor.models import (
    CommCareCase,
    LedgerTransaction,
    LedgerValue,
    XFormInstance,
)
from corehq.form_processor.utils.sql import fetchall_as_namedtuple
from corehq.sql_db.config import plproxy_config
from corehq.sql_db.util import (
    estimate_row_count,
    get_db_aliases_for_partitioned_query,
    split_list_by_db_partition,
)

doc_type_to_state = XFormInstance.DOC_TYPE_TO_STATE


def iter_all_rows(reindex_accessor):
    """Returns a generator that will iterate over all rows provided by the
    reindex accessor
    """
    for db_alias in reindex_accessor.sql_db_aliases:
        docs = reindex_accessor.get_docs(db_alias)
        while docs:
            for doc in docs:
                yield doc

            last_id = getattr(doc, reindex_accessor.primary_key_field_name)
            docs = reindex_accessor.get_docs(db_alias, last_doc_pk=last_id)


def iter_all_ids(reindex_accessor):
    return itertools.chain.from_iterable(iter_all_ids_chunked(reindex_accessor))


def iter_all_ids_chunked(reindex_accessor):
    for db_alias in reindex_accessor.sql_db_aliases:
        docs = list(reindex_accessor.get_doc_ids(db_alias))
        while docs:
            yield [d.doc_id for d in docs]

            last_id = docs[-1].primary_key
            docs = list(reindex_accessor.get_doc_ids(db_alias, last_doc_pk=last_id))


class ShardAccessor(object):
    hash_key = b'\x00' * 16

    @staticmethod
    def hash_doc_ids_sql_for_testing(doc_ids):
        """Get HASH for each doc_id from PostgreSQL

        This is used to ensure the python version is consistent with what's
        being used by PL/Proxy
        """
        assert settings.USE_PARTITIONED_DATABASE

        params = ','.join(["(%s)"] * len(doc_ids))
        query = """
            SELECT doc_id, hash_string(doc_id, 'siphash24') AS hash
            FROM (VALUES {}) AS t (doc_id)
        """.format(params)
        with XFormInstance.get_plproxy_cursor() as cursor:
            cursor.execute(query, doc_ids)
            rows = fetchall_as_namedtuple(cursor)
            return {row.doc_id: row.hash for row in rows}

    @staticmethod
    def hash_doc_uuid_sql_for_testing(doc_uuid):
        """Get the hash for a UUID from PostgreSQL

        This is used to ensure the python version is consistent with what's
        being used by PL/Proxy
        """
        assert settings.USE_PARTITIONED_DATABASE

        if not isinstance(doc_uuid, UUID):
            raise ValueError("Expected an instance of UUID")

        query = "SELECT hash_string(CAST(%s AS bytea), 'siphash24') AS hash"
        with XFormInstance.get_plproxy_cursor() as cursor:
            doc_uuid_before_cast = '\\x%s' % doc_uuid.hex
            cursor.execute(query, [doc_uuid_before_cast])
            return cursor.fetchone()[0]

    @staticmethod
    def hash_doc_ids_python(doc_ids):
        return {
            doc_id: ShardAccessor.hash_doc_id_python(doc_id)
            for doc_id in doc_ids
        }

    @staticmethod
    def hash_doc_id_python(doc_id):
        if isinstance(doc_id, str):
            doc_id = doc_id.encode('utf-8')
        elif isinstance(doc_id, UUID):
            # Hash the 16-byte string
            doc_id = doc_id.bytes

        digest = csiphash.siphash24(ShardAccessor.hash_key, doc_id)
        hash_long = struct.unpack("<Q", digest)[0]  # convert byte string to long
        # convert 64 bit hash to 32 bit to match Postgres
        return hash_long & 0xffffffff

    @staticmethod
    def get_database_for_docs(doc_ids):
        """
        :param doc_ids:
        :return: Dict of ``doc_id -> Django DB alias``
        """
        return ShardAccessor._get_doc_database_map(doc_ids, by_doc=True)

    @staticmethod
    def get_docs_by_database(doc_ids):
        """
        :param doc_ids:
        :return: Dict of ``Django DB alias -> doc_id``
        """
        return ShardAccessor._get_doc_database_map(doc_ids, by_doc=False)

    @staticmethod
    def _get_doc_database_map(doc_ids, by_doc=True):
        assert settings.USE_PARTITIONED_DATABASE, """Partitioned DB not in use,
        consider using `corehq.sql_db.get_db_alias_for_partitioned_doc` instead"""
        databases = {}
        shard_map = plproxy_config.get_django_shard_map()
        part_mask = len(shard_map) - 1
        for chunk in chunked(doc_ids, 100):
            hashes = ShardAccessor.hash_doc_ids_python(chunk)
            shards = {doc_id: hash_ & part_mask for doc_id, hash_ in hashes.items()}
            for doc_id, shard_id in shards.items():
                dbname = shard_map[shard_id].django_dbname
                if by_doc:
                    databases.update({
                        doc_id: dbname
                    })
                else:
                    if dbname not in databases:
                        databases[dbname] = [doc_id]
                    else:
                        databases[dbname].append(doc_id)
        return databases

    @staticmethod
    def get_shard_id_and_database_for_doc(doc_id):
        assert settings.USE_PARTITIONED_DATABASE, """Partitioned DB not in use,
        consider using `corehq.sql_db.get_db_alias_for_partitioned_doc` instead"""
        shard_map = plproxy_config.get_django_shard_map()
        part_mask = len(shard_map) - 1
        hash_ = ShardAccessor.hash_doc_id_python(doc_id)
        shard_id = hash_ & part_mask
        return shard_id, shard_map[shard_id].django_dbname

    @staticmethod
    def get_database_for_doc(doc_id):
        """
        :return: Django DB alias in which the doc should be stored
        """
        return ShardAccessor.get_shard_id_and_database_for_doc(doc_id)[1]


DocIds = namedtuple('DocIds', 'doc_id primary_key')


class ReindexAccessor(metaclass=ABCMeta):
    primary_key_field_name = 'id'

    def __init__(self, limit_db_aliases=None):
        self.limit_db_aliases = limit_db_aliases

    def is_sharded(self):
        """
        :return: True the django model is sharded, otherwise false.
        """
        from corehq.sql_db.models import PartitionedModel
        return issubclass(self.model_class, PartitionedModel)

    @property
    def sql_db_aliases(self):
        all_db_aliases = get_db_aliases_for_partitioned_query() if self.is_sharded() \
            else [router.db_for_read(self.model_class)]
        if self.limit_db_aliases:
            db_aliases = list(set(all_db_aliases) & set(self.limit_db_aliases))
            assert db_aliases, 'Limited DBs not in expected list: {} {}'.format(
                all_db_aliases, self.limit_db_aliases
            )
            return db_aliases
        return all_db_aliases

    @abstractproperty
    def model_class(self):
        """
        :return: the django model class belonging to this reindexer
        """
        raise NotImplementedError

    @abstractproperty
    def id_field(self):
        """
        :return: The name of the model field to return when calling ``get_doc_ids``. Return a string
                 or a dict mapping an alias to a SQL expression
        """
        raise NotImplementedError

    @abstractmethod
    def get_doc(self, doc_id):
        """
        :param doc_id: ID of the doc
        :return: The doc with the given ID
        """
        raise NotImplementedError

    def doc_to_json(self, doc):
        """
        :param doc:
        :return: The JSON representation of the doc
        """
        return doc.to_json()

    def filters(self, last_doc_pk=None, for_count=False):
        filters = []
        if last_doc_pk is not None:
            filters.append(Q(**{self.primary_key_field_name + "__gt": last_doc_pk}))
        filters.extend(self.extra_filters(for_count=for_count))
        return functools.reduce(operator.and_, filters) if filters else None

    def query(self, from_db, last_doc_pk=None, for_count=False):
        filters = self.filters(last_doc_pk, for_count)
        query = self.model_class.objects.using(from_db)
        if filters:
            query = query.filter(filters)
        return query

    def get_doc_ids(self, from_db, last_doc_pk=None, limit=500):
        """
        :param from_db: The DB alias to query
        :param last_doc_pk: The primary key of the last doc from the previous batch
        :param limit: Desired batch size
        :return: Generator of DocIds namedtuple
        """
        query = self.query(from_db, last_doc_pk)
        field = self.id_field
        if isinstance(field, dict):
            query = query.annotate(**field)
            field = list(field)[0]
        query = query.values(self.primary_key_field_name, field)
        for row in query.order_by(self.primary_key_field_name)[:limit]:
            yield DocIds(row[field], row[self.primary_key_field_name])

    def get_docs(self, from_db, last_doc_pk=None, limit=500):
        """Get a batch of
        :param from_db: The DB alias to query
        :param last_doc_pk: The primary key of the last doc from the previous batch
        :param limit: Desired batch size
        :return: List of documents
        """
        query = self.query(from_db, last_doc_pk)
        return query.order_by(self.primary_key_field_name)[:limit]

    def extra_filters(self, for_count=False):
        """
        :param for_count: True if only filters required for the count query. Only simple filters
                          should be included for the count query.
        :return: list of sql filters
        """
        return []

    def get_approximate_doc_count(self, from_db):
        """Get the approximate doc count from the given DB

        :param from_db: The DB alias to query
        """
        query = self.query(from_db, for_count=True)
        return estimate_row_count(query, from_db)


class FormReindexAccessor(ReindexAccessor):

    def __init__(self, domain=None, include_attachments=True, limit_db_aliases=None, include_deleted=False,
                 start_date=None, end_date=None):
        super(FormReindexAccessor, self).__init__(limit_db_aliases)
        self.domain = domain
        self.include_attachments = include_attachments
        self.include_deleted = include_deleted
        self.start_date = start_date
        self.end_date = end_date

    @property
    def model_class(self):
        return XFormInstance

    @property
    def id_field(self):
        return 'form_id'

    def get_doc(self, doc_id):
        try:
            return XFormInstance.objects.get_form(doc_id, self.domain)
        except XFormNotFound:
            pass

    def doc_to_json(self, doc):
        try:
            return doc.to_json(include_attachments=self.include_attachments)
        except MissingFormXml:
            return {}

    def extra_filters(self, for_count=False):
        filters = []
        if not (for_count or self.include_deleted):
            # don't include in count query since the query planner can't account for it
            filters.append(Q(deleted_on__isnull=True))
        if self.domain:
            filters.append(Q(domain=self.domain))
        if self.start_date is not None:
            filters.append(Q(received_on__gte=self.start_date))
        if self.end_date is not None:
            filters.append(Q(received_on__lt=self.end_date))
        return filters


class CaseReindexAccessor(ReindexAccessor):
    """
    :param: domain: If supplied the accessor will restrict results to only that domain
    """
    def __init__(self, domain=None, limit_db_aliases=None, start_date=None, end_date=None, case_type=None,
                 include_deleted=False):
        super(CaseReindexAccessor, self).__init__(limit_db_aliases=limit_db_aliases)
        self.domain = domain
        self.start_date = start_date
        self.end_date = end_date
        self.case_type = case_type
        self.include_deleted = include_deleted

    @property
    def model_class(self):
        return CommCareCase

    @property
    def id_field(self):
        return 'case_id'

    def get_doc(self, doc_id):
        try:
            return CommCareCase.objects.get_case(doc_id)
        except CaseNotFound:
            pass

    def extra_filters(self, for_count=False):
        filters = [] if self.include_deleted else [Q(deleted=False)]
        if self.domain:
            filters.append(Q(domain=self.domain))
        if self.start_date is not None:
            filters.append(Q(server_modified_on__gte=self.start_date))
        if self.end_date is not None:
            filters.append(Q(server_modified_on__lt=self.end_date))
        if self.case_type is not None:
            filters.append(Q(type=self.case_type))
        return filters


class LedgerReindexAccessor(ReindexAccessor):

    def __init__(self, domain=None, limit_db_aliases=None):
        super(LedgerReindexAccessor, self).__init__(limit_db_aliases=limit_db_aliases)
        self.domain = domain

    @property
    def model_class(self):
        return LedgerValue

    @property
    def id_field(self):
        slash = Value('/')
        return {
            'ledger_reference': Concat('case_id', slash, 'section_id', slash, 'entry_id')
        }

    def get_doc(self, doc_id):
        from corehq.form_processor.parsers.ledgers.helpers import UniqueLedgerReference
        ref = UniqueLedgerReference.from_id(doc_id)
        try:
            return LedgerAccessorSQL.get_ledger_value(**ref._asdict())
        except CaseNotFound:
            pass

    def extra_filters(self, for_count=False):
        if self.domain:
            return [Q(domain=self.domain)]
        return []

    def doc_to_json(self, doc):
        json_doc = doc.to_json()
        json_doc['_id'] = doc.ledger_reference.as_id()
        return json_doc


class LedgerAccessorSQL(AbstractLedgerAccessor):

    @staticmethod
    def get_ledger_values_for_cases(case_ids, section_ids=None, entry_ids=None, date_start=None, date_end=None):
        assert isinstance(case_ids, list)
        if not case_ids:
            return []

        if section_ids:
            assert isinstance(section_ids, list)
        if entry_ids:
            assert isinstance(entry_ids, list)

        return list(LedgerValue.objects.plproxy_raw(
            'SELECT * FROM get_ledger_values_for_cases_3(%s, %s, %s, %s, %s)',
            [case_ids, section_ids, entry_ids, date_start, date_end]
        ))

    @staticmethod
    def get_ledger_values_for_case(case_id):
        return list(LedgerValue.objects.plproxy_raw(
            'SELECT * FROM get_ledger_values_for_cases_3(%s)',
            [[case_id]]
        ))

    @staticmethod
    def get_ledger_value(case_id, section_id, entry_id):
        try:
            return LedgerValue.objects.plproxy_raw(
                'SELECT * FROM get_ledger_value(%s, %s, %s)',
                [case_id, section_id, entry_id]
            )[0]
        except IndexError:
            raise LedgerValueNotFound

    @staticmethod
    def save_ledger_values(ledger_values, stock_result=None):
        if not ledger_values and not (stock_result and stock_result.cases_with_deprecated_transactions):
            return

        try:
            if stock_result and stock_result.cases_with_deprecated_transactions:
                db_cases = split_list_by_db_partition(stock_result.cases_with_deprecated_transactions)
                for db_name, case_ids in db_cases:
                    LedgerTransaction.objects.using(db_name).filter(
                        case_id__in=case_ids,
                        form_id=stock_result.xform.form_id
                    ).delete()

            for ledger_value in ledger_values:
                transactions_to_save = ledger_value.get_live_tracked_models(LedgerTransaction)

                with transaction.atomic(using=ledger_value.db, savepoint=False):
                    ledger_value.save()
                    for trans in transactions_to_save:
                        trans.save()

                ledger_value.clear_tracked_models()
        except InternalError as e:
            raise LedgerSaveError(e)

    @staticmethod
    def get_ledger_transactions_for_case(case_id, section_id=None, entry_id=None):
        return list(LedgerTransaction.objects.plproxy_raw(
            "SELECT * FROM get_ledger_transactions_for_case(%s, %s, %s)",
            [case_id, section_id, entry_id]
        ))

    @staticmethod
    def get_ledger_transactions_in_window(case_id, section_id, entry_id, window_start, window_end):
        return list(LedgerTransaction.objects.plproxy_raw(
            "SELECT * FROM get_ledger_transactions_for_case(%s, %s, %s, %s, %s)",
            [case_id, section_id, entry_id, window_start, window_end]
        ))

    @staticmethod
    def get_transactions_for_consumption(domain, case_id, product_id, section_id, window_start, window_end):
        from corehq.apps.commtrack.consumption import should_exclude_invalid_periods
        transactions = LedgerAccessorSQL.get_ledger_transactions_in_window(
            case_id, section_id, product_id, window_start, window_end
        )
        exclude_inferred_receipts = should_exclude_invalid_periods(domain)
        return itertools.chain.from_iterable([
            transaction.get_consumption_transactions(exclude_inferred_receipts)
            for transaction in transactions
        ])

    @staticmethod
    def get_latest_transaction(case_id, section_id, entry_id):
        try:
            return LedgerTransaction.objects.plproxy_raw(
                "SELECT * FROM get_latest_ledger_transaction(%s, %s, %s)",
                [case_id, section_id, entry_id]
            )[0]
        except IndexError:
            return None

    @staticmethod
    def get_current_ledger_state(case_ids, ensure_form_id=False):
        ledger_values = LedgerValue.objects.plproxy_raw(
            'SELECT * FROM get_ledger_values_for_cases_3(%s)',
            [case_ids]
        )
        ret = {case_id: {} for case_id in case_ids}
        for value in ledger_values:
            sections = ret[value.case_id].setdefault(value.section_id, {})
            sections[value.entry_id] = value

        return ret

    @staticmethod
    def delete_ledger_transactions_for_form(case_ids, form_id):
        """
        Delete LedgerTransactions for form.
        :param case_ids: list of case IDs which ledger transactions belong to (required for correct sharding)
        :param form_id:  ID of the form
        :return: number of transactions deleted
        """
        assert isinstance(case_ids, list)
        with LedgerTransaction.get_plproxy_cursor() as cursor:
            cursor.execute(
                "SELECT delete_ledger_transactions_for_form(%s, %s) as deleted_count",
                [case_ids, form_id]
            )
            results = fetchall_as_namedtuple(cursor)
            return sum([result.deleted_count for result in results])

    @staticmethod
    def delete_ledger_values(case_id, section_id=None, entry_id=None):
        """
        Delete LedgerValues marching passed in args
        :param case_id:    ID of the case
        :param section_id: section ID or None
        :param entry_id:   entry ID or None
        :return: number of values deleted
        """
        try:
            with LedgerValue.get_plproxy_cursor() as cursor:
                cursor.execute(
                    "SELECT delete_ledger_values(%s, %s, %s) as deleted_count",
                    [case_id, section_id, entry_id]
                )
                results = fetchall_as_namedtuple(cursor)
                return sum([result.deleted_count for result in results])
        except InternalError as e:
            raise LedgerSaveError(e)

    @staticmethod
    def get_ledger_transactions_for_form(form_id, limit_to_cases):
        for db_name, case_ids in split_list_by_db_partition(limit_to_cases):
            resultset = LedgerTransaction.objects.using(db_name).filter(
                case_id__in=case_ids, form_id=form_id
            )
            for trans in resultset:
                yield trans
