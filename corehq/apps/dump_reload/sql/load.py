from __future__ import unicode_literals

import json
from collections import defaultdict

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

from corehq.form_processor.backends.sql.dbaccessors import ShardAccessor
from corehq.sql_db.config import partition_config


partitioned_model_id_fields = {
    'form_processor.XFormInstanceSQL': 'form_id',
    'form_processor.XFormAttachmentSQL': 'form',
    'form_processor.XFormOperationSQL': 'form',
}


def load_sql_data(data_file):
    """
    Loads data from a given file.
    :return: tuple(total object count, loaded object count)
    """
    # Keep a count of the installed objects
    loaded_object_count = 0
    total_object_count = 0

    def _process_chunk(chunk):
        global total_object_count, loaded_object_count
        chunk_total, chunk_loaded = load_objects(chunk)
        total_object_count += len(chunk)
        loaded_object_count += chunk_loaded

    chunk = []
    for line in data_file:
        chunk.append(json.load(line))
        if len(chunk) >= 1000:
            _process_chunk(chunk)
            chunk = []

    if chunk:
        _process_chunk(chunk)

    return total_object_count, loaded_object_count


def load_objects(objects):
    loaded_object_count = 0

    for db_alias, objects_for_db in _group_objects_by_db(objects):
        with transaction.atomic(using=db_alias):
            loaded_objects = load_data_for_db(db_alias, objects)
        loaded_object_count += loaded_objects

    return loaded_object_count


def load_data_for_db(db_alias, objects):
    connection = connections[db_alias]

    loaded_object_count = 0
    models = set()
    with connection.constraint_checks_disabled():
        for obj in PythonDeserializer(objects, using=db_alias):
            if router.allow_migrate_model(db_alias, obj.object.__class__):
                loaded_object_count += 1
                models.add(obj.object.__class__)
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
    table_names = [model._meta.db_table for model in models]
    try:
        connection.check_constraints(table_names=table_names)
    except Exception as e:
        e.args = ("Problem loading data: %s" % e,)
        raise

    # If we found even one object, we need to reset the database sequences.
    if loaded_object_count > 0:
        sequence_sql = connection.ops.sequence_reset_sql(no_style(), models)
        if sequence_sql:
            with connection.cursor() as cursor:
                for line in sequence_sql:
                    cursor.execute(line)
    return loaded_object_count


def _group_objects_by_db(objects):
    objects_by_db = defaultdict(list)
    for obj in objects:
        app_label = obj['model']
        model = apps.get_model(app_label)
        db_alias = router.db_for_write(model)
        if settings.USE_PARTITIONED_DATABASE and db_alias == partition_config.get_proxy_db():
            doc_id = _get_doc_id(app_label, obj)
            db_alias = ShardAccessor.get_database_for_doc(doc_id)

        objects_by_db[db_alias].append(obj)
    return objects_by_db.items()


def _get_doc_id(app_label, model_json):
    field = partitioned_model_id_fields[app_label]
    return model_json[field]
