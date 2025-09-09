from collections import defaultdict
from datetime import UTC, datetime, timedelta

from couchdbkit import ResourceNotFound

from django.core.cache import cache as _django_cache

from pillowtop.logger import pillow_logging

from corehq.sql_db.connections import connection_manager
from corehq.util.soft_assert import soft_assert

from .exceptions import StaleRebuildError, TableRebuildError
from .rebuild import (
    get_table_diffs,
    get_tables_rebuild_migrate,
    migrate_tables,
)
from .sql import get_metadata
from .tasks import rebuild_indicators

LAST_TASK_RUN_KEY_PREFIX = 'last-task-run'


def _is_datasource_active(adapter):
    """
    Tries to fetch a fresh copy of datasource from couchdb to know whether it is active.
    If it does not exist then it assumed to be deactivated
    """
    try:
        config_id = adapter.config._id
        config = adapter.config.get(config_id)
    except ResourceNotFound:
        return False
    return not config.is_deactivated


def rebuild_sql_tables(adapters):

    def _notify_rebuild(msg, obj):
        assert_ = soft_assert(notify_admins=True)
        assert_(False, msg, obj)

    tables_by_engine = defaultdict(dict)
    all_adapters = []
    for adapter in adapters:
        if getattr(adapter, 'all_adapters', None):
            all_adapters.extend(adapter.all_adapters)
        else:
            all_adapters.append(adapter)
    for adapter in all_adapters:
        if _is_datasource_active(adapter):
            tables_by_engine[adapter.engine_id][adapter.get_table().name] = adapter
        else:
            pillow_logging.info(
                f"""[rebuild] Tried to rebuild deactivated data source.
                Id - {adapter.config._id}
                Domain {adapter.config.domain}.
                Skipping."""
            )
    for engine_id, table_map in tables_by_engine.items():
        table_names = list(table_map)
        engine = connection_manager.get_engine(engine_id)

        diffs = get_table_diffs(engine, table_names, get_metadata(engine_id))

        tables_to_act_on = get_tables_rebuild_migrate(diffs)
        for table_name in tables_to_act_on.rebuild:
            sql_adapter = table_map[table_name]
            pillow_logging.info(
                "[rebuild] Rebuilding table: %s, from config %s at rev %s",
                table_name, sql_adapter.config._id, sql_adapter.config._rev
            )
            pillow_logging.info("[rebuild] Using config: %r", sql_adapter.config)
            pillow_logging.info("[rebuild] sqlalchemy metadata: %r", get_metadata(engine_id).tables[table_name])
            pillow_logging.info("[rebuild] sqlalchemy table: %r", sql_adapter.get_table())
            table_diffs = [diff for diff in diffs if diff.table_name == table_name]
            if not sql_adapter.config.is_static:
                try:
                    rebuild_table(sql_adapter, table_diffs)
                except TableRebuildError as e:
                    _notify_rebuild(str(e), sql_adapter.config.to_json())
            else:
                rebuild_table(sql_adapter, table_diffs)

        migrate_tables_with_logging(engine, diffs, tables_to_act_on.migrate, table_map)


def migrate_tables_with_logging(engine, diffs, table_names, adapters_by_table):
    migration_diffs = [diff for diff in diffs if diff.table_name in table_names]
    for table in table_names:
        adapter = adapters_by_table[table]
        pillow_logging.info("[rebuild] Using config: %r", adapter.config)
        pillow_logging.info("[rebuild] sqlalchemy metadata: %r", get_metadata(adapter.engine_id).tables[table])
        pillow_logging.info("[rebuild] sqlalchemy table: %r", adapter.get_table())
    changes = migrate_tables(engine, migration_diffs)
    for table, diffs in changes.items():
        adapter = adapters_by_table[table]
        pillow_logging.info(
            "[rebuild] Migrating table: %s, from config %s at rev %s",
            table, adapter.config._id, adapter.config._rev
        )
        adapter.log_table_migrate(source='pillowtop', diffs=diffs)


def rebuild_table(adapter, diffs=None):
    config = adapter.config
    if not config.is_static:
        latest_rev = config.get_db().get_rev(config._id)
        if config._rev != latest_rev:
            raise StaleRebuildError('Tried to rebuild a stale table ({})! Ignoring...'.format(config))

    diff_dicts = [diff.to_dict() for diff in diffs]
    if config.disable_destructive_rebuild and adapter.table_exists:
        adapter.log_table_rebuild_skipped(source='pillowtop', diffs=diff_dicts)
        return

    rebuild_indicators.delay(
        adapter.config.get_id,
        source='pillowtop',
        engine_id=adapter.engine_id,
        diffs=diff_dicts,
        domain=config.domain,
    )


class TaskCoordinator:
    """Coordinate tasks that need to be run on a periodic basis

    Answer the question of whether a task should run based on time
    elapsed since it was last run. For multiple concurrent actors,
    exactly one will be allowed to run a task during each interval.
    """

    def __init__(self, name, interval, django_cache=_django_cache):
        self.name = name
        self.interval = timedelta(seconds=interval)
        self.django_cache = django_cache
        self.local_cache = {}

    def should_run(self, task_key):
        """Return True if the task should be run

        :param task_key: A unique key for the task. The string value of
            the key must be unique for each task, so for example '100'
            (str) and 100 (int) have the same key value.
        """
        now = datetime.now(UTC)
        last_run = self.local_cache.get(task_key)
        if last_run and last_run + self.interval > now:
            return False

        key = self._get_key(task_key)
        timeout = self.interval.total_seconds()
        for i in range(2):
            if self.django_cache.add(key, now, timeout=timeout):
                self._update_local_cache(task_key, now)
                return True

            last_run = self.django_cache.get(key, now)
            buffer = timedelta(seconds=10)  # avoid expiration after add
            if last_run + self.interval + buffer > now:
                self._update_local_cache(task_key, last_run)
                break  # key timeout in django cache is not too long

            assert i == 0, f"tried to delete {key!r} with too long timeout " \
                "twice, this should never happen"
            # Current interval is shorter than the cache timeout. This
            # can happen if the interval is changed to a shorter value.
            # Delete it and try again.
            self.django_cache.delete(key)

        return False

    def reset(self, task_key):
        """Reset the task so that it should run again

        Note: the local cache may prevent concurrent actors from
        noticing a reset. It may need to be removed if that feature
        is needed.
        """
        key = self._get_key(task_key)
        self.django_cache.delete(key)
        self.local_cache.pop(task_key, None)

    def _get_key(self, task_key):
        """Get the django cache key for the task"""
        return f"{LAST_TASK_RUN_KEY_PREFIX}:{self.name}:{task_key}"

    def _update_local_cache(self, task_key, now):
        """Remove expired entries from local cache"""
        cache = self.local_cache
        cache[task_key] = now
        cutoff = now - self.interval
        for key, last_rebuild in list(cache.items()):
            if last_rebuild < cutoff:
                cache.pop(key, None)
