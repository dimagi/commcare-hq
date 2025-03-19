import hashlib
import random
import re
import uuid
from collections import defaultdict
from looseversion import LooseVersion
from functools import wraps

from django.conf import settings
from django.db import OperationalError, connections, transaction
from django.db.utils import DEFAULT_DB_ALIAS, DatabaseError
from django.db.utils import InterfaceError as DjangoInterfaceError

from corehq.sql_db.config import plproxy_config, plproxy_standby_config
from corehq.util.metrics.load_counters import load_counter_for_model
from corehq.util.quickcache import quickcache
from memoized import memoized
from psycopg2._psycopg import InterfaceError as Psycopg2InterfaceError

ACCEPTABLE_STANDBY_DELAY_SECONDS = 3
STALE_CHECK_FREQUENCY = 30

PG_V10 = LooseVersion('10.0.0')

REPLICATION_SQL_10 = """
    SELECT
    CASE
        WHEN NOT EXISTS (SELECT 1 FROM pg_stat_wal_receiver) THEN -1
        WHEN pg_last_wal_receive_lsn() = pg_last_wal_replay_lsn() THEN 0
        ELSE GREATEST(0, EXTRACT (EPOCH FROM now() - pg_last_xact_replay_timestamp()))
    END
    AS replication_lag;
    """

REPLICATION_SQL_9_6 = """
    SELECT
    CASE
        WHEN NOT EXISTS (SELECT 1 FROM pg_stat_wal_receiver) THEN -1
        WHEN pg_last_xlog_receive_location() = pg_last_xlog_replay_location() THEN 0
        ELSE EXTRACT (EPOCH FROM now() - pg_last_xact_replay_timestamp())::INTEGER
    END
    AS replication_lag;
    """


def paginate_query_across_partitioned_databases(model_class, q_expression, annotate=None, query_size=5000,
                                                values=None, load_source=None):
    """
    Runs a query across all partitioned databases in small chunks and produces a generator
    with the results.

    :param model_class: A Django model class

    :param q_expression: An instance of django.db.models.Q representing the
    filter to apply

    :param annotate: (optional) If specified, should be a dictionary of annotated fields
    and their calculations. The dictionary will be splatted into the `.annotate` function

    :param values: (optional) If specified, should be a list of values to retrieve rather
    than retrieving entire objects.

    :return: A generator with the results
    """
    db_names = get_db_aliases_for_partitioned_query()
    for db_name in db_names:
        for row in paginate_query(db_name, model_class, q_expression, annotate, query_size, values, load_source):
            yield row


def paginate_query(db_name, model_class, q_expression, annotate=None, query_size=5000, values=None,
                   load_source=None):
    """
    Runs a query on the given database in small chunks and produces a generator
    with the results.

    Iteration logic adopted from https://djangosnippets.org/snippets/1949/

    :param model_class: A Django model class

    :param q_expression: An instance of django.db.models.Q representing the
    filter to apply

    :param annotate: (optional) If specified, should be a dictionary of annotated fields
    and their calculations. The dictionary will be splatted into the `.annotate` function

    :param values: (optional) If specified, should be a list of values to retrieve rather
    than retrieving entire objects.

    :return: A generator with the results
    """

    track_load = load_counter_for_model(model_class)(load_source, None)
    sort_col = 'pk'

    return_values = None
    if values:
        return_values = [sort_col] + values

    qs = model_class.objects.using(db_name)
    if annotate:
        qs = qs.annotate(**annotate)

    qs = qs.filter(q_expression).order_by(sort_col)

    if return_values:
        qs = qs.values_list(*return_values)

    filter_expression = {}
    while True:
        results = qs.filter(**filter_expression)[:query_size]
        for row in results:
            track_load()
            if return_values:
                value = row[0]
                yield row[1:]
            else:
                value = row.pk
                yield row

        if len(results) < query_size:
            break

        filter_expression = {'{}__gt'.format(sort_col): value}


def estimate_partitioned_row_count(model_class, q_expression):
    """Estimate query row count summed across all partitions"""
    db_names = get_db_aliases_for_partitioned_query()
    query = model_class.objects.using(db_names[0]).filter(q_expression)
    return estimate_row_count(query, db_names)


def estimate_row_count(query, db_name="default"):
    """Estimate query row count

    Source:
    https://www.citusdata.com/blog/2016/10/12/count-performance/#dup_counts_estimated_filtered

    :param query: A queryset or two-tuple `(<SQL string>, <bind params>)`.
    :param db_name: A database name (str) or sequence of database names
    to query. The sum of counts from all databases will be returned.
    """
    def count(db_name):
        with connections[db_name].cursor() as cursor:
            cursor.execute(sql, params)
            lines = [line for line, in cursor.fetchall()]
            for line in lines:
                match = rows_expr.search(line)
                if match:
                    return int(match.group(1))
            return 0

    rows_expr = re.compile(r" rows=(\d+) ")
    if hasattr(query, "query"):
        sql, params = query.query.sql_with_params()
    else:
        sql, params = query
    sql = f"EXPLAIN {sql}"
    if isinstance(db_name, str):
        return count(db_name)
    return sum(count(db_) for db_ in db_name)


def split_list_by_db_partition(partition_values):
    """
    :param partition_values: Iterable of partition values (e.g. case IDs)
    :return: list of tuples (db_name, list(partition_values))
    """
    mapping = defaultdict(list)
    for value in partition_values:
        db_name = get_db_alias_for_partitioned_doc(value)
        mapping[db_name].append(value)
    return list(mapping.items())


def get_db_alias_for_partitioned_doc(partition_value):
    if settings.USE_PARTITIONED_DATABASE:
        from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
        db_name = ShardAccessor.get_database_for_doc(partition_value)
    else:
        db_name = DEFAULT_DB_ALIAS
    return db_name


def get_db_aliases_for_partitioned_query():
    if settings.USE_PARTITIONED_DATABASE:
        db_names = plproxy_config.form_processing_dbs
    else:
        db_names = [DEFAULT_DB_ALIAS]
    return db_names


def get_default_db_aliases():
    return [DEFAULT_DB_ALIAS]


def get_all_db_aliases():
    return list(settings.DATABASES)


def get_default_and_partitioned_db_aliases():
    return list(set(get_db_aliases_for_partitioned_query() + get_default_db_aliases()))


def new_id_in_same_dbalias(partition_value):
    """
    Returns a new partition value that belongs to the same db alias as
        the given partition value does
    """
    old_db_name = get_db_alias_for_partitioned_doc(partition_value)
    new_db_name = None
    while old_db_name != new_db_name:
        # todo; guard against infinite recursion
        new_partition_value = str(uuid.uuid4())
        new_db_name = get_db_alias_for_partitioned_doc(new_partition_value)
    return new_partition_value


def handle_connection_failure(get_db_aliases=get_default_db_aliases):
    def _inner2(fn):
        @wraps(fn)
        def _inner(*args, **kwargs):
            try:
                return fn(*args, **kwargs)
            except DatabaseError:
                # we have to do this manually to avoid issues with
                # open transactions and already closed connections
                for db_name in get_db_aliases():
                    transaction.rollback(using=db_name)

                # re raise the exception for additional error handling
                raise
            except (Psycopg2InterfaceError, DjangoInterfaceError):
                # force closing the connection to prevent Django from trying to reuse it.
                # http://www.tryolabs.com/Blog/2014/02/12/long-time-running-process-and-django-orm/
                for db_name in get_db_aliases():
                    connections[db_name].close()

                # re raise the exception for additional error handling
                raise

        return _inner

    return _inner2


def get_all_sharded_models():
    from corehq.sql_db.models import PartitionedModel
    for subclass in _get_all_nested_subclasses(PartitionedModel):
        if not subclass._meta.abstract:
            yield subclass


def _get_all_nested_subclasses(cls):
    seen = set()
    for subclass in cls.__subclasses__():
        for sub_subclass in _get_all_nested_subclasses(subclass):
            # in case of multiple inheritance
            if sub_subclass not in seen:
                seen.add(sub_subclass)
                yield sub_subclass
        if subclass not in seen:
            seen.add(subclass)
            yield subclass


@memoized
def get_standby_databases():
    standby_dbs = set()
    for db_alias in settings.DATABASES:
        with connections[db_alias].cursor() as cursor:
            cursor.execute("SELECT pg_is_in_recovery()")
            [(is_standby, )] = cursor.fetchall()
            if is_standby:
                standby_dbs.add(db_alias)
    return standby_dbs


@memoized
def get_db_version(db_alias):
    with connections[db_alias].cursor() as cursor:
        cursor.execute('SHOW SERVER_VERSION;')
        raw_version = cursor.fetchone()[0]

    return LooseVersion(raw_version.split(' ')[0])


def get_replication_delay_for_standby(db_alias):
    """
    Finds the replication delay for given database by running a SQL query on standby database.
        See https://www.postgresql.org/message-id/CADKbJJWz9M0swPT3oqe8f9+tfD4-F54uE6Xtkh4nERpVsQnjnw@mail.gmail.com

    If standby process (wal_receiver) is not running on standby -1 is returned
    """
    # used to indicate that the wal_receiver process on standby is not running
    try:
        sql = REPLICATION_SQL_10 if get_db_version(db_alias) >= PG_V10 else REPLICATION_SQL_9_6
        with connections[db_alias].cursor() as cursor:
            cursor.execute(sql)
            [(delay, )] = cursor.fetchall()
            return delay
    except OperationalError:
        return -1


def get_replication_delay_for_shard_standbys():
    db_to_django_alias = {
        settings.DATABASES[db_alias]['NAME']: db_alias
        for db_alias in plproxy_standby_config.form_processing_dbs
    }

    return {
        db_to_django_alias[row[0]]: row[1]
        for row in _get_replication_delay_results_from_proxy()
    }


def _get_replication_delay_results_from_proxy():
    try:
        with connections[plproxy_standby_config.proxy_db].cursor() as cursor:
            cursor.execute('select * from get_replication_delay()')
            return cursor.fetchall()
    except OperationalError:
        return []


@memoized
def get_acceptible_replication_delays():
    """This returns a dict mapping DB alias to max replication delay.
    Note: this assigns a default value to any DB that does not have
    an explicit value set (including master databases)."""
    ret = {}
    for db_, config in settings.DATABASES.items():
        delay = config.get('STANDBY', {}).get('ACCEPTABLE_REPLICATION_DELAY')
        if delay is None:
            # try legacy setting
            delay = config.get('HQ_ACCEPTABLE_STANDBY_DELAY')
            if delay is None:
                delay = ACCEPTABLE_STANDBY_DELAY_SECONDS

        ret[db_] = delay
    return ret


@quickcache(
    [], timeout=STALE_CHECK_FREQUENCY, skip_arg=lambda *args: settings.UNIT_TESTING,
    memoize_timeout=STALE_CHECK_FREQUENCY, session_function=None
)
def get_standbys_with_acceptible_delay():
    """:returns: set of database aliases that are configured as standbys and have replication
                 delay below the configured threshold
    """
    acceptable_delays_by_db = get_acceptible_replication_delays()
    standbys = get_standby_databases()

    delays_by_db = {}
    if plproxy_standby_config:
        standbys -= set(plproxy_standby_config.form_processing_dbs)
        delays_by_db = get_replication_delay_for_shard_standbys()

    delays_by_db.update({
        db_: get_replication_delay_for_standby(db_)
        for db_ in standbys
    })

    return {
        db_ for db_, delay in delays_by_db.items()
        if 0 <= (-1 if delay is None else delay) <= acceptable_delays_by_db[db_]
    }


def get_databases_for_read_query(candidate_dbs):
    all_standbys = get_standby_databases()
    queryable_standbys = get_standbys_with_acceptible_delay()
    masters = candidate_dbs - all_standbys
    ok_standbys = candidate_dbs & queryable_standbys
    return masters | ok_standbys


def select_db_for_read(weighted_dbs):
    """
    Returns a randomly selected database per the weights assigned from
        a list of databases. If any database is standby and its replication has
        more than acceptable delay, that db is dropped from selection

    Args:
        weighted_dbs: a list of tuple of db and the weight.
            [
                ("pgmain", 5),
                ("pgmainstandby", 5)
            ]

    """
    if not weighted_dbs:
        return

    weights_by_db = {db_: weight for db_, weight in weighted_dbs}
    fresh_dbs = get_databases_for_read_query(set(weights_by_db))

    dbs = []
    weights = []
    for _db, weight in weights_by_db.items():
        if _db in fresh_dbs:
            dbs.append(_db)
            weights.append(weight)

    if dbs:
        return random.choices(dbs, weights=weights)[0]


def select_plproxy_db_for_read(primary_db):
    if not plproxy_standby_config:
        return primary_db

    if primary_db == plproxy_config.proxy_db:
        plproxy_shard_standbys = set(plproxy_standby_config.form_processing_dbs)
        ok_standbys = get_standbys_with_acceptible_delay() & plproxy_shard_standbys
        if ok_standbys == plproxy_shard_standbys:
            # require ALL standbys to be available
            return plproxy_standby_config.proxy_db
        else:
            return primary_db
    else:
        standbys = primary_to_standbys_mapping()[primary_db]
        ok_standbys = get_standbys_with_acceptible_delay() & standbys
        if ok_standbys:
            return random.choice(list(ok_standbys))
        else:
            return primary_db


@memoized
def primary_to_standbys_mapping():
    mapping = defaultdict(set)
    for db, config in settings.DATABASES.items():
        master = config.get('STANDBY', {}).get('MASTER')
        if master:
            mapping[master].add(db)
    return mapping


def create_unique_index_name(app, table, fields):
    assert all([app, table, fields]), "app, table, and fields must be specified"
    assert type(fields) == list, "fields must be a list"

    max_length = 30  # enforced by Django
    index_name = f"{app}_{table}_{'_'.join(fields)}_idx"
    if len(index_name) > max_length:
        # hash the index name and take the first 9 characters
        hashed = hashlib.sha1(index_name.encode("UTF-8")).hexdigest()[:8]
        index_name = f"{index_name[:17]}_{hashed}_idx"
    return index_name
