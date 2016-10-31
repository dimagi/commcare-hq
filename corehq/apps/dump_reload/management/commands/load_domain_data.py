from __future__ import unicode_literals

import gzip
import os
import warnings
import zipfile

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.sql import load_sql_data


class Command(BaseCommand):
    help = 'Loads data from the give file into the database.'
    args = '<dump file path>'

    def handle(self, dump_file_path, **options):
        self.verbosity = options.get('verbosity')

        self.compression_formats = {
            None: (open, 'rb'),
            'gz': (gzip.GzipFile, 'rb'),
            'zip': (SingleZipReader, 'r'),
        }

        if not os.path.isfile(dump_file_path):
            raise CommandError("Dump file not found: {}".format(dump_file_path))

        if self.verbosity >= 2:
            self.stdout.write("Installing data from %s." % dump_file_path)

        cmp_fmt = self.get_compression_format(os.path.basename(dump_file_path))
        open_method, mode = self.compression_formats[cmp_fmt]
        dump_file = open_method(dump_file_path, mode)
        try:
            total_object_count, loaded_object_count = load_sql_data(dump_file)
        except Exception as e:
            if not isinstance(e, CommandError):
                e.args = ("Problem installing data '%s': %s" % (dump_file_path, e),)
            raise
        finally:
            dump_file.close()

        # Warn if the file we loaded contains 0 objects.
        if loaded_object_count == 0:
            warnings.warn(
                "No data found for '%s'. (File format may be "
                "invalid.)" % dump_file_path,
                RuntimeWarning
            )

        if self.verbosity >= 1:
            if total_object_count == loaded_object_count:
                self.stdout.write("Installed %d object(s)" % loaded_object_count)
            else:
                self.stdout.write("Installed %d object(s) (of %d)" %
                                  (loaded_object_count, total_object_count))

    def get_compression_format(self, file_name):
        parts = file_name.rsplit('.', 1)

        if len(parts) > 1 and parts[-1] in self.compression_formats:
            cmp_fmt = parts[-1]
        else:
            cmp_fmt = None

        return cmp_fmt


class SingleZipReader(zipfile.ZipFile):

    def __init__(self, *args, **kwargs):
        zipfile.ZipFile.__init__(self, *args, **kwargs)
        if len(self.namelist()) != 1:
            raise ValueError("Zip-compressed data file must contain one file.")

    def read(self):
        return zipfile.ZipFile.read(self, self.namelist()[0])
