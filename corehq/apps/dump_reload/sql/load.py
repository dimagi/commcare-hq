import json
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
import multiprocessing as mp

from django.apps import apps
from django.conf import settings
from django.core.management.color import no_style
from django.core.serializers.python import Deserializer as PythonDeserializer
from django.db import (
    DatabaseError,
    IntegrityError,
    connections,
    router,
    transaction,
)
from django.utils.encoding import force_text

from corehq.apps.dump_reload.exceptions import DataLoadException
from corehq.apps.dump_reload.interface import DataLoader
from corehq.apps.dump_reload.util import get_model_label
from corehq.sql_db.routers import HINT_PARTITION_VALUE

CHUNK_SIZE = 200


class DefaultDictWithKey(defaultdict):
    """
    A defaultdict that passes ``key`` to its factory
    """
    def __missing__(self, key):
        self[key] = value = self.default_factory(key)
        return value


class LoadStat(object):
    """Simple object for keeping track of stats"""
    def __init__(self, db_alias, model_counter):
        self.db_alias = db_alias
        self.model_counter = model_counter

    def update(self, stat):
        """
        :type stat: LoadStat
        """
        assert self.db_alias == stat.db_alias
        self.model_counter += stat.model_counter


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
            worker_tasks = {wq[0] for wq in dbalias_to_workerqueue.values()}
            return [t.result() for t in as_completed(worker_tasks)]

        num_aliases = len(settings.DATABASES)
        manager = mp.Manager()
        with ProcessPoolExecutor(max_workers=num_aliases) as executor:
            # Map each db_alias to a queue + a worker task to consume the queue
            worker_queue_factory = partial(get_worker_queue, executor, manager)
            # DefaultDictWithKey passes the key to its factory function so that
            # the worker knows its db_alias without having to figure it out
            dbalias_to_workerqueue = DefaultDictWithKey(worker_queue_factory)

            for line in object_strings:
                obj = self.line_to_object(line)
                if obj:
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
    load_stat = LoadStat(db_alias, Counter())

    def process(chunk_):
        nonlocal load_stat
        with transaction.atomic(using=db_alias):
            stat = load_data_for_db(db_alias, chunk_)
        load_stat.update(stat)
        chunk_.clear()

    chunk = []
    while True:
        obj = queue.get()
        if obj is None:  # None is used as a terminator
            break
        chunk.append(obj)
        try:
            if len(chunk) == CHUNK_SIZE:
                process(chunk)
        finally:
            queue.task_done()
    try:
        if chunk:
            process(chunk)
    finally:
        queue.task_done()
    return load_stat


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


def load_data_for_db(db_alias, objects):
    """
    :param db_alias: Django alias for database to load objects into
    :param objects: List of object dictionaries to load
    :return: LoadStats object
    """
    connection = connections[db_alias]

    model_counter = Counter()
    with connection.constraint_checks_disabled():
        for obj in PythonDeserializer(objects, using=db_alias):
            if router.allow_migrate_model(db_alias, obj.object.__class__):
                model_counter.update([obj.object.__class__])
                try:
                    obj.save(using=db_alias)
                except (DatabaseError, IntegrityError) as e:
                    e.args = ("Could not load %(app_label)s.%(object_name)s(pk=%(pk)s): %(error_msg)s" % {
                        'app_label': obj.object._meta.app_label,
                        'object_name': obj.object._meta.object_name,
                        'pk': obj.object.pk,
                        'error_msg': force_text(e)
                    },)
                    raise

    # Since we disabled constraint checks, we must manually check for
    # any invalid keys that might have been added
    table_names = [model._meta.db_table for model in model_counter]
    try:
        connection.check_constraints(table_names=table_names)
    except Exception as e:
        e.args = ("Problem loading data: %s" % e,)
        raise

    return LoadStat(db_alias, model_counter)


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
            field = [
                field for field in model._meta.fields
                if field.column == model.partition_attr
            ][0]
            try:
                partition_value = obj['fields'][field.name]
            except KeyError:
                if model.partition_attr == model._meta.pk.attname:
                    partition_value = obj['pk']
                else:
                    raise DataLoadException(f"Unable to find field {app_label}.{model.partition_attr}")

        router_hints[HINT_PARTITION_VALUE] = partition_value
    return router.db_for_write(model, **router_hints)
