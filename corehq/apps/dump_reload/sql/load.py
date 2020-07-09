import json
import multiprocessing as mp
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor as Executor
from contextlib import contextmanager
from functools import partial

from django.apps import apps
from django.conf import settings
from django.core.management.color import no_style
from django.core.serializers.python import Deserializer as PythonDeserializer
from django.db import (
    DatabaseError,
    connections,
    router,
    transaction,
)

from corehq.apps.dump_reload.exceptions import DataLoadException
from corehq.apps.dump_reload.interface import DataLoader
from corehq.apps.dump_reload.util import get_model_label
from corehq.sql_db.routers import HINT_PARTITION_VALUE

CHUNK_SIZE = 200


class SqlDataLoader(DataLoader):
    slug = 'sql'

    def load_objects(self, object_strings, force=False):
        object_count = 0

        def enqueue_object(dbalias_to_workerqueue, obj):
            nonlocal object_count
            db_alias = get_db_alias(obj)
            __, queue = dbalias_to_workerqueue[db_alias]
            queue.put(obj)
            object_count += 1
            if not object_count % 1000:
                self.stdout.write(f'Loaded {object_count} SQL objects')

        def terminate_workers(dbalias_to_workerqueue):
            for __, queue in dbalias_to_workerqueue.values():
                queue.put(None)

        def collect_stats(dbalias_to_workerqueue):
            return [w.result() for w, q in dbalias_to_workerqueue.values()]

        num_aliases = len(settings.DATABASES)
        manager = mp.Manager()
        with Executor(max_workers=num_aliases) as executor:
            # Map each db_alias to a queue + a worker task to consume the queue
            worker_queue_factory = partial(get_worker_queue, executor, manager)
            # DefaultDictWithKey passes the key to its factory function so that
            # the worker knows its db_alias without having to figure it out
            dbalias_to_workerqueue = DefaultDictWithKey(worker_queue_factory)

            for line in object_strings:
                obj = self.line_to_object(line)
                if obj is not None:
                    enqueue_object(dbalias_to_workerqueue, obj)
            terminate_workers(dbalias_to_workerqueue)
            load_stats = collect_stats(dbalias_to_workerqueue)

        _reset_sequences(load_stats)
        loaded_model_counts = Counter()
        for db_stats in load_stats:
            model_labels = (f'(sql) {get_model_label(model)}'
                            for model in db_stats.model_counter.elements())
            loaded_model_counts.update(model_labels)
        return object_count, loaded_model_counts

    def line_to_object(self, line):
        line = line.strip()
        if line:
            obj = json.loads(line)
            if self.filter_object(obj):
                return obj
        return None

    def filter_object(self, object):
        if not self.object_filter:
            return True
        model_label = object['model']
        return self.object_filter.findall(model_label)


def get_worker_queue(process_pool_executor, manager, db_alias):
    """
    Instantiates a queue, and starts a worker task in its own process
    """
    queue = manager.JoinableQueue(maxsize=CHUNK_SIZE)
    worker_task = process_pool_executor.submit(worker, queue, db_alias)
    return worker_task, queue


def worker(queue, db_alias):
    """
    Pulls objects from queue and loads them into their DB.
    """
    coro = load_data_for_db(db_alias)
    next(coro)
    while True:
        obj = queue.get()
        if obj is None:
            load_stat = coro.send(None)
            queue.task_done()
            return load_stat
        coro.send(obj)
        queue.task_done()


def _reset_sequences(load_stats):
    """Reset DB sequences if needed"""
    for stat in load_stats:
        loaded_object_count = sum(stat.model_counter.values())
        if loaded_object_count > 0:
            connection = connections[stat.db_alias]
            models = list(stat.model_counter)
            sequence_sql = connection.ops.sequence_reset_sql(no_style(), models)
            if sequence_sql:
                with connection.cursor() as cursor:
                    for line in sequence_sql:
                        cursor.execute(line)


def load_data_for_db(db_alias):
    """
    A coroutine that is sent object dictionaries and loads them into the
    database identified by ``db_alias``. When it is terminated with
    ``None``, it yields a LoadStat object.
    """
    model_counter = Counter()
    with constraint_checks_deferred(db_alias), \
            transaction.atomic(using=db_alias):
        while True:
            obj_dict = yield
            if obj_dict is None:
                break
            for obj in PythonDeserializer([obj_dict], using=db_alias):
                Model = type(obj.object)
                if not router.allow_migrate_model(db_alias, Model):
                    continue
                model_counter.update([Model])
                try:
                    obj.save(using=db_alias)
                except DatabaseError as err:
                    m = Model._meta
                    raise type(err)(
                        f'Could not load {m.app_label}.{m.object_name}'
                        f'(pk={obj.object.pk}) in DB {db_alias!r}'
                    ) from err
    print(f'Loading DB {db_alias!r} complete')
    yield LoadStat(db_alias, model_counter)


@contextmanager
def constraint_checks_deferred(db_alias):
    """
    PostgreSQL does not support disabling constraint checks like MySQL.
    But you can defer them until transaction commit. Django's
    ``DatabaseWrapper`` for PostgreSQL doesn't have a method for this,
    so we need to execute raw SQL.
    """
    connection = connections[db_alias]
    with connection.cursor() as cursor:
        cursor.execute('SET CONSTRAINTS ALL DEFERRED')
        try:
            yield
        finally:
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')


def get_db_alias(obj: dict) -> str:
    app_label = obj['model']
    model = apps.get_model(app_label)
    router_hints = {}
    if hasattr(model, 'partition_attr'):
        try:
            partition_value = obj['fields'][model.partition_attr]
        except KeyError:
            # in the case of foreign keys the serialized field name is the
            # name of the foreign key attribute
            field, = [
                field for field in model._meta.fields
                if field.column == model.partition_attr
            ]
            try:
                partition_value = obj['fields'][field.name]
            except KeyError:
                if model.partition_attr == model._meta.pk.attname:
                    partition_value = obj['pk']
                else:
                    raise DataLoadException(f"Unable to find field {app_label}.{model.partition_attr}")

        router_hints[HINT_PARTITION_VALUE] = partition_value
    return router.db_for_write(model, **router_hints)


class DefaultDictWithKey(defaultdict):
    """
    A defaultdict that passes ``key`` to its factory
    """
    def __missing__(self, key):
        self[key] = value = self.default_factory(key)
        return value


class LoadStat:
    """
    Simple object for keeping track of stats
    """
    def __init__(self, db_alias, model_counter):
        self.db_alias = db_alias
        self.model_counter = model_counter

    def update(self, stat: 'LoadStat'):
        assert self.db_alias == stat.db_alias
        self.model_counter += stat.model_counter
