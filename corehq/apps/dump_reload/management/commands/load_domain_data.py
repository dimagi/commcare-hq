import json
import os
import zipfile
import inspect

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
    """This command expects a ZIP file containing one or more
    gzip files and a 'meta.json' file containing doc counts for each
    of the gzip files:

    zip:
       sql.gz
       couch.gz
       sql-other.gz
       meta.json

    The filenames of the gzip files must be formatted as <slug><suffix>.gz where
        -  <slug> is one of 'sql', 'couch', 'domain', 'toggle'
        -  <suffix> can be anything

    meta.json:
        Must contain a single JSON object with properties for each of the filnames
        in the zip file. The value of the properties must be a dict of
        document counts in the corresponding gzip file:

            {
                "domain": {"Domain": 1},
                "sql": {"blobs.BlobMeta": 11, "auth.User": 1},
                "couch": {"users.CommCareUser": 5},
                "toggles": {"Toggle": 5},
            }
    """
    help = inspect.cleandoc("""
        Loads data from the give file into the database.

        Use in conjunction with `dump_domain_data`.
    """)

    def add_arguments(self, parser):
        parser.add_argument('dump_file_path')
        parser.add_argument('--use-extracted', action='store_true', default=False, dest='use_extracted',
                            help="Use already extracted dump if it exists.")
        parser.add_argument('--force', action='store_true', default=False, dest='force',
                            help="Load data for domain that already exists.")
        parser.add_argument('--dry-run', action='store_true', default=False, dest='dry_run',
                            help="Skip saving data to the DB")
        parser.add_argument('--loader', dest='loaders', action='append', default=[],
                            help='loader slug to run (use multiple --loader to run multiple loaders).'
                                 'domain should always be the first loader to be invoked in case of '
                                 'very first import',
                            choices=[loader.slug for loader in LOADERS])
        parser.add_argument('--object-filter',
                            help="Regular expression to use to selectively load data. Will be matched"
                                 " against a CouchDB 'doc_type' or Django model name: 'app_label.ModelName'."
                                 "Use 'print_domain_stats' command to get a list of available types.")
        parser.add_argument('--json-output', action="store_true", help="Produce JSON output for use in tests")
        parser.add_argument('--chunksize', type=int, default=100,
                            help="Set custom chunksize in case it runs into large couch documents")
        parser.add_argument('--throttle', action="store_false", help="Throttle saves to database")

    def handle(self, dump_file_path, **options):
        self.force = options.get('force')
        self.dry_run = options.get('dry_run')
        self.use_extracted = options.get('use_extracted')
        self.chunksize = options.get('chunksize')
        self.should_throttle = options.get('throttle')

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
            loaded_meta.update(self._load_data(loader, extracted_dir, object_filter, dump_meta))

        if options.get("json_output"):
            return json.dumps(loaded_meta)
        else:
            self._print_stats(loaded_meta, dump_meta)

    def _print_stats(self, loaded_meta, dump_meta):
        self.stdout.write('{0} Load Stats {0}'.format('-' * 40))
        for loader, models in sorted(loaded_meta.items()):
            self.stdout.write(loader)
            for model, count in sorted(models.items()):
                expected = dump_meta[loader].get(model, 0)
                self.stdout.write(f"  {model:<50}: {count} / {expected}")
        self.stdout.write('{0}{0}'.format('-' * 46))
        loaded_object_count = sum(count for model in loaded_meta.values() for count in model.values())
        total_object_count = sum(count for model in dump_meta.values() for count in model.values())
        self.stdout.write(f'Loaded {loaded_object_count}/{total_object_count} objects')
        self.stdout.write('{0}{0}'.format('-' * 46))

    def extract_dump_archive(self, dump_file_path):
        target_dir = get_tmp_extract_dir(dump_file_path)
        if not os.path.exists(target_dir):
            with zipfile.ZipFile(dump_file_path, 'r') as archive:
                archive.extractall(target_dir)
        elif not self.use_extracted:
            raise CommandError(
                "Extracted dump already exists at {}. Delete it or use --use-extracted".format(target_dir))
        return target_dir

    def _load_data(self, loader_class, extracted_dump_path, object_filter, dump_meta):
        try:
            loader = loader_class(object_filter, self.stdout, self.stderr, self.chunksize, self.should_throttle)
            return loader.load_from_path(extracted_dump_path, dump_meta, force=self.force, dry_run=self.dry_run)
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


def get_tmp_extract_dir(dump_file_path, specifier=""):
    return f'_tmp_load_{specifier}_{dump_file_path}'
