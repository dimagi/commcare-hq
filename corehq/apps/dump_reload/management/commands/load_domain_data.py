from __future__ import unicode_literals

import os
import zipfile
from collections import Counter
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

        if not os.path.isfile(dump_file_path):
            raise CommandError("Dump file not found: {}".format(dump_file_path))

        if self.verbosity >= 2:
            self.stdout.write("Loading data from %s." % dump_file_path)

        utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        target_dir = '_tmp_load_{}'.format(utcnow)
        with zipfile.ZipFile(dump_file_path, 'r') as archive:
            archive.extractall(target_dir)

        total_object_count = 0
        model_counts = Counter()
        for loader in [SqlDataLoader, CouchDataLoader]:
            loader_total_object_count, loader_model_counts = self._load_data(loader, target_dir)
            total_object_count += loader_total_object_count
            model_counts.update(loader_model_counts)

        loaded_object_count = sum(model_counts.values())

        if self.verbosity >= 2:
            print '{0} Load Stats {0}'.format('-' * 32)
            for model in sorted(model_counts):
                print "{:<40}: {}".format(model, model_counts[model])
            print '{0}{0}'.format('-' * 38)
            print 'Loaded {}/{} objects'.format(loaded_object_count, total_object_count)
            print '{0}{0}'.format('-' * 38)
        else:
            self.stdout.write("Loaded %d object(s) (of %d)" %
                              (loaded_object_count, total_object_count))

    def _load_data(self, loader_class, extracted_dump_path):
        try:
            return loader_class().load_from_file(extracted_dump_path)
        except Exception as e:
            if not isinstance(e, CommandError):
                e.args = ("Problem loading data '%s': %s" % (extracted_dump_path, e),)
            raise
