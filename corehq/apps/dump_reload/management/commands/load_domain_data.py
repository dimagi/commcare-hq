import json
import os
import zipfile

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.couch.load import (
    CouchDataLoader,
    DomainLoader,
    ToggleLoader,
)
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
        parser.add_argument('--skip', dest='skip', action='append', default=[],
                            help='Skip over the first n objects for the specified loader.  '
                            '`--skip=sql:1000` skips the first 1000 objects in the sql dump')
        parser.add_argument('--object-filter',
                            help="Regular expression to use to selectively load data. Will be matched"
                                 " against a CouchDB 'doc_type' or Django model name: 'app_label.ModelName'."
                                 "Use 'print_domain_stats' command to get a list of available types.")

    def handle(self, dump_file_path, **options):
        self.force = options.get('force')
        self.use_extracted = options.get('use_extracted')
        skip = {slug: int(count) for slug, count in
                (s.split(':') for s in options.get('skip'))}

        if not os.path.isfile(dump_file_path):
            raise CommandError("Dump file not found: {}".format(dump_file_path))

        self.stdout.write("Loading data from %s." % dump_file_path)
        extracted_dir = self.extract_dump_archive(dump_file_path)

        loaded_meta = {}
        loaders = options.get('loaders')
        object_filter = options.get('object_filter')
        if loaders:
            loaders = [loader for loader in LOADERS if loader.slug in loaders]
        else:
            loaders = LOADERS

        dump_meta = _get_dump_meta(extracted_dir)
        for loader in loaders:
            loaded_meta[loader.slug] = self._load_data(
                loader, extracted_dir, object_filter, skip.get(loader.slug), dump_meta)

        self._print_stats(loaded_meta, dump_meta)

    def _print_stats(self, loaded_meta, dump_meta):
        self.stdout.write('{0} Load Stats {0}'.format('-' * 40))
        for loader, models in sorted(loaded_meta.items()):
            self.stdout.write(loader)
            for model, count in sorted(models.items()):
                expected = dump_meta[loader][model]
                self.stdout.write(f"  {model:<50}: {count} / {expected}")
        self.stdout.write('{0}{0}'.format('-' * 46))
        loaded_object_count = sum(count for model in loaded_meta.values() for count in model.values())
        total_object_count = sum(count for model in dump_meta.values() for count in model.values())
        self.stdout.write(f'Loaded {loaded_object_count}/{total_object_count} objects')
        self.stdout.write('{0}{0}'.format('-' * 46))

    def extract_dump_archive(self, dump_file_path):
        target_dir = '_tmp_load_{}'.format(dump_file_path)
        if not os.path.exists(target_dir):
            with zipfile.ZipFile(dump_file_path, 'r') as archive:
                archive.extractall(target_dir)
        elif not self.use_extracted:
            raise CommandError(
                "Extracted dump already exists at {}. Delete it or use --use-extracted".format(target_dir))
        return target_dir

    def _load_data(self, loader_class, extracted_dump_path, object_filter, skip, dump_meta):
        try:
            loader = loader_class(object_filter, skip, self.stdout, self.stderr)
            return loader.load_from_file(extracted_dump_path, dump_meta, force=self.force)
        except DataExistsException as e:
            raise CommandError('Some data already exists. Use --force to load anyway: {}'.format(str(e)))
        except Exception as e:
            if not isinstance(e, CommandError):
                e.args = ("Problem loading data '%s': %s" % (extracted_dump_path, e),)
            raise


def _get_dump_meta(extracted_dir):
    # The dump command should have a metadata json file of the form
    # {dumper_slug: {model_name: count}}
    meta_path = os.path.join(extracted_dir, 'meta.json')
    with open(meta_path) as f:
        return json.loads(f.read())
