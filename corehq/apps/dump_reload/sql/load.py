
import json
from collections import defaultdict, namedtuple, Counter

from django.apps import apps
from django.conf import settings
from django.core.management.color import no_style
from django.core.serializers.python import (
    Deserializer as PythonDeserializer,
)
from django.db import (
    DatabaseError, IntegrityError, connections, router,
    transaction,
)
from django.utils.encoding import force_text

from corehq.apps.dump_reload.interface import DataLoader
from corehq.apps.dump_reload.util import get_model_label
from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.sql_db.config import partition_config


PARTITIONED_MODEL_SHARD_ID_FIELDS = {
    'form_processor.xforminstancesql': 'form_id',
    'form_processor.xformattachmentsql': 'form',
    'form_processor.xformoperationsql': 'form',
    'form_processor.commcarecasesql': 'case_id',
    'form_processor.commcarecaseindexsql': 'case',
    'form_processor.casetransaction': 'case',
    'form_processor.ledgervalue': 'case',
    'form_processor.ledgertransaction': 'case',
    'blobs.blobmeta': 'parent_id',
}


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
        # Keep a count of the installed objects
        load_stats_by_db = {}
        total_object_counts = []

        def _process_chunk(chunk, total_object_counts=total_object_counts, load_stats_by_db=load_stats_by_db):
            chunk_stats = load_objects(chunk)
            total_object_counts.append(len(chunk))
            self.stdout.write('Loaded {} SQL objects'.format(sum(total_object_counts)))
            _update_stats(load_stats_by_db, chunk_stats)

        chunk = []
        for line in object_strings:
            line = line.strip()
            if not line:
                continue
            chunk.append(json.loads(line))
            if len(chunk) >= 1000:
                _process_chunk(chunk)
                chunk = []

        if chunk:
            _process_chunk(chunk)

        _reset_sequences(list(load_stats_by_db.values()))

        loaded_model_counts = Counter()
        for db_stats in load_stats_by_db.values():
            model_labels = ('(sql) {}'.format(get_model_label(model)) for model in db_stats.model_counter.elements())
            loaded_model_counts.update(model_labels)

        return sum(total_object_counts), loaded_model_counts


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


def load_objects(objects):
    """Load the given list of object dictionaries into the database
    :return: List of LoadStat objects
    """
    load_stats_by_db = {}

    for db_alias, objects_for_db in _group_objects_by_db(objects):
        with transaction.atomic(using=db_alias):
            load_stat = load_data_for_db(db_alias, objects_for_db)

        _update_stats(load_stats_by_db, [load_stat])

    return list(load_stats_by_db.values())


def _update_stats(current_stats_by_db, new_stats):
    """Helper to update stats dictionary"""
    for new_stat in new_stats:
        current_stat = current_stats_by_db.get(new_stat.db_alias)
        if current_stat is not None:
            current_stat.update(new_stat)
        else:
            current_stats_by_db[new_stat.db_alias] = new_stat


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


def _group_objects_by_db(objects):
    """
    :param objects: Deserialized object dictionaries
    :return: List of tuples of (db_alias, [object,...])
    """
    objects_by_db = defaultdict(list)
    for obj in objects:
        app_label = obj['model']
        model = apps.get_model(app_label)
        db_alias = router.db_for_write(model)
        if settings.USE_PARTITIONED_DATABASE and db_alias == partition_config.get_proxy_db():
            doc_id = _get_doc_id(app_label, obj)
            db_alias = ShardAccessor.get_database_for_doc(doc_id)

        objects_by_db[db_alias].append(obj)
    return list(objects_by_db.items())


def _get_doc_id(app_label, model_json):
    field = PARTITIONED_MODEL_SHARD_ID_FIELDS[app_label]
    return model_json['fields'][field]
