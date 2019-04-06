from __future__ import unicode_literals

from __future__ import absolute_import
import os
import six
import zipfile
from collections import Counter

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.couch.load import CouchDataLoader, ToggleLoader, DomainLoader
from corehq.apps.dump_reload.exceptions import DataExistsException
from corehq.apps.dump_reload.sql import SqlDataLoader


# Domain loader should be first
LOADERS = [DomainLoader, SqlDataLoader, CouchDataLoader, ToggleLoader]


class Command(BaseCommand):
    help = 'Loads data from the give file into the database.'

    def add_arguments(self, parser):
        parser.add_argument('dump_file_path')
        parser.add_argument('--use-extracted', action='store_true', default=False, dest='use_extracted',
                            help="Use already extracted dump if it exists.")
        parser.add_argument('--force', action='store_true', default=False, dest='force',
                            help="Load data for domain that already exists.")
        parser.add_argument('--loader', dest='loaders', action='append', default=[],
                            help='loader slug to run (use multiple --loader to run multiple loaders).'
                                 'domain should always be the first loader to be invoked in case of '
                                 'very first import',
                            choices=[loader.slug for loader in LOADERS])

    def handle(self, dump_file_path, **options):
        self.verbosity = options.get('verbosity')
        self.force = options.get('force')
        self.use_extracted = options.get('use_extracted')

        if not os.path.isfile(dump_file_path):
            raise CommandError("Dump file not found: {}".format(dump_file_path))

        if self.verbosity >= 2:
            self.stdout.write("Loading data from %s." % dump_file_path)

        extracted_dir = self.extract_dump_archive(dump_file_path)

        total_object_count = 0
        model_counts = Counter()
        loaders = options.get('loaders')
        if loaders:
            loaders = [loader for loader in LOADERS if loader.slug in loaders]
        else:
            loaders = LOADERS

        for loader in loaders:
            loader_total_object_count, loader_model_counts = self._load_data(loader, extracted_dir)
            total_object_count += loader_total_object_count
            model_counts.update(loader_model_counts)

        loaded_object_count = sum(model_counts.values())

        if self.verbosity >= 2:
            self.stdout.write('{0} Load Stats {0}'.format('-' * 40))
            for model in sorted(model_counts):
                self.stdout.write("{:<48}: {}".format(model, model_counts[model]))
            self.stdout.write('{0}{0}'.format('-' * 46))
            self.stdout.write('Loaded {}/{} objects'.format(loaded_object_count, total_object_count))
            self.stdout.write('{0}{0}'.format('-' * 46))
        else:
            self.stdout.write("Loaded %d object(s) (of %d)" %
                              (loaded_object_count, total_object_count))

    def extract_dump_archive(self, dump_file_path):
        target_dir = '_tmp_load_{}'.format(dump_file_path)
        if not os.path.exists(target_dir):
            with zipfile.ZipFile(dump_file_path, 'r') as archive:
                archive.extractall(target_dir)
        elif not self.use_extracted:
            raise CommandError(
                "Extracted dump already exists at {}. Delete it or use --use-extracted".format(target_dir))
        return target_dir

    def _load_data(self, loader_class, extracted_dump_path):
        try:
            return loader_class(self.stdout, self.stderr).load_from_file(extracted_dump_path, self.force)
        except DataExistsException as e:
            raise CommandError('Some data already exists. Use --force to load anyway: {}'.format(six.text_type(e)))
        except Exception as e:
            if not isinstance(e, CommandError):
                e.args = ("Problem loading data '%s': %s" % (extracted_dump_path, e),)
            raise
