from __future__ import unicode_literals

import gzip
import os
import warnings
import zipfile

from datetime import datetime
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch.load import CouchDataLoader
from corehq.apps.dump_reload.sql import SqlDataLoader


class Command(BaseCommand):
    help = 'Loads data from the give file into the database.'
    args = '<dump file path>'

    def handle(self, dump_file_path, **options):
        self.verbosity = options.get('verbosity')

        _check_file(dump_file_path)

        if self.verbosity >= 2:
            self.stdout.write("Installing data from %s." % dump_file_path)

        utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        target_dir = '_tmp_load_{}'.format(utcnow)
        with zipfile.ZipFile(dump_file_path, 'r') as archive:
            archive.extractall(target_dir)

        sql_dump_path = os.path.join(target_dir, 'sql.gz')
        couch_dump_path = os.path.join(target_dir, 'couch.gz')

        _check_file(sql_dump_path)
        _check_file(couch_dump_path)

        loaded_object_count_sql, total_object_count_sql = self._load_data(SqlDataLoader, sql_dump_path)
        loaded_object_count_couch, total_object_count_couch = self._load_data(CouchDataLoader, sql_dump_path)

        total_object_count = total_object_count_sql + total_object_count_couch
        loaded_object_count = loaded_object_count_sql + loaded_object_count_couch
        if self.verbosity >= 1:
            if total_object_count == loaded_object_count:
                self.stdout.write("Installed %d object(s)" % loaded_object_count)
            else:
                self.stdout.write("Installed %d object(s) (of %d)" %
                                  (loaded_object_count, total_object_count))

    def _load_data(self, parser_class, dump_path):
        with gzip.open(dump_path) as dump_file:
            try:
                total_object_count, loaded_object_count = parser_class().load_objects(dump_file)
            except Exception as e:
                if not isinstance(e, CommandError):
                    e.args = ("Problem installing data '%s': %s" % (dump_path, e),)
                raise

        # Warn if the file we loaded contains 0 objects.
        if loaded_object_count == 0:
            warnings.warn(
                "No data found for '%s'. (File format may be "
                "invalid.)" % dump_path,
                RuntimeWarning
            )

        return loaded_object_count, total_object_count


def _check_file(path):
    if not os.path.isfile(path):
        raise CommandError("Dump file not found: {}".format(path))
