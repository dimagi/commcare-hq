from __future__ import unicode_literals

import gzip
import json
import os
import warnings
import zipfile
from collections import defaultdict

from django.apps import apps
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
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


class Command(BaseCommand):
    help = 'Loads data from the give file into the database.'
    args = '<dump file path>'

    def handle(self, dump_file_path, **options):
        self.verbosity = options.get('verbosity')

        # Keep a count of the installed objects
        self.loaded_object_count = 0
        self.total_object_count = 0

        self.compression_formats = {
            None: (open, 'rb'),
            'gz': (gzip.GzipFile, 'rb'),
            'zip': (SingleZipReader, 'r'),
        }

        if not os.path.isfile(dump_file_path):
            raise CommandError("Dump file not found: {}".format(dump_file_path))

        self.load_data(dump_file_path)

        if self.verbosity >= 1:
            if self.total_object_count == self.loaded_object_count:
                self.stdout.write("Installed %d object(s)" % self.loaded_object_count)
            else:
                self.stdout.write("Installed %d object(s) (of %d)" %
                                  (self.loaded_object_count, self.total_object_count))

    def load_data(self, dump_file_path):
        """
        Loads data from a given file.
        """
        cmp_fmt = self.get_compression_format(os.path.basename(dump_file_path))
        open_method, mode = self.compression_formats[cmp_fmt]
        dump_file = open_method(dump_file_path, mode)
        try:
            if self.verbosity >= 2:
                self.stdout.write("Installing data from %s." % dump_file_path)

            objects = json.load(dump_file)
            for db_alias, objects_for_db in _group_objects_by_db(objects):
                with transaction.atomic(using=db_alias):
                    loaded_objects, num_objects = self.load_data_for_db(db_alias, objects)
                self.loaded_object_count += loaded_objects
                self.total_object_count += num_objects
        except Exception as e:
            if not isinstance(e, CommandError):
                e.args = ("Problem installing data '%s': %s" % (dump_file_path, e),)
            raise
        finally:
            dump_file.close()

        # Warn if the file we loaded contains 0 objects.
        if self.loaded_object_count == 0:
            warnings.warn(
                "No data found for '%s'. (File format may be "
                "invalid.)" % dump_file_path,
                RuntimeWarning
            )

    def load_data_for_db(self, db_alias, objects):
        connection = connections[db_alias]

        objects_count = 0
        loaded_object_count = 0
        models = set()
        with connection.constraint_checks_disabled():
            for obj in PythonDeserializer(objects, using=db_alias):
                objects_count += 1
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
                if self.verbosity >= 2:
                    self.stdout.write("Resetting sequences\n")
                with connection.cursor() as cursor:
                    for line in sequence_sql:
                        print line
                        cursor.execute(line)
        return loaded_object_count, objects_count

    def get_compression_format(self, file_name):
        parts = file_name.rsplit('.', 1)

        if len(parts) > 1 and parts[-1] in self.compression_formats:
            cmp_fmt = parts[-1]
        else:
            cmp_fmt = None

        return cmp_fmt


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


class SingleZipReader(zipfile.ZipFile):

    def __init__(self, *args, **kwargs):
        zipfile.ZipFile.__init__(self, *args, **kwargs)
        if len(self.namelist()) != 1:
            raise ValueError("Zip-compressed data file must contain one file.")

    def read(self):
        return zipfile.ZipFile.read(self, self.namelist()[0])
