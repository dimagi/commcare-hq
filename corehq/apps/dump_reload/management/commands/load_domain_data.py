import json
import os

from django.core.management.base import BaseCommand, CommandError

from corehq.apps.dump_reload.archive import (
    ExtractedDumpExistsError,
    ZipWithZstdArchiveReader,
    ZippedGzipArchiveReader,
)
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
    """Loads a dump produced by ``dump_domain_data``.

    The archive's ``meta.json`` summarises object counts per loader::

        {
            "domain": {"Domain": 1},
            "sql": {"blobs.BlobMeta": 11, "auth.User": 1},
            "couch": {"users.CommCareUser": 5},
            "toggles": {"Toggle": 5},
        }
    """

    help = (
        "Loads data from the given file into the database.\n\n"
        "Use in conjunction with `dump_domain_data`."
    )

    def add_arguments(self, parser):
        parser.add_argument('dump_file_path')
        parser.add_argument('--format', choices=['gzip', 'zstd'], default='gzip',
                            help='Archive format of the input file.')
        parser.add_argument('--use-extracted', action='store_true', default=False, dest='use_extracted',
                            help="Use already extracted dump if it exists "
                                 "(gzip format only; ignored otherwise).")
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
            raise CommandError(f"Dump file not found: {dump_file_path}")

        self.stdout.write(f"Loading data from {dump_file_path}.")

        archive_format = options.get('format')
        try:
            if archive_format == 'gzip':
                archive = ZippedGzipArchiveReader(dump_file_path, use_extracted=self.use_extracted)
            else:
                archive = ZipWithZstdArchiveReader(dump_file_path)
        except ValueError as e:
            raise CommandError(str(e))

        loaded_meta = {}
        requested_loaders = options.get('loaders')
        object_filter = options.get('object_filter')
        loaders = [loader for loader in LOADERS if not requested_loaders or loader.slug in requested_loaders]

        try:
            with archive:
                for loader in loaders:
                    loaded_meta.update(self._load_data(loader, archive, object_filter))
        except ExtractedDumpExistsError as e:
            raise CommandError(
                f"Extracted dump already exists at {e.path}. Delete it or use --use-extracted"
            )

        if options.get("json_output"):
            return json.dumps(loaded_meta)
        else:
            self._print_stats(loaded_meta, archive.meta)

    def _load_data(self, loader_class, archive, object_filter):
        try:
            loader = loader_class(object_filter, self.stdout, self.stderr, self.chunksize, self.should_throttle)
            with archive.open_stream(loader.slug) as stream:
                return loader.load_from_stream(stream, stream.meta, force=self.force, dry_run=self.dry_run)
        except DataExistsException as e:
            raise CommandError(f"Some data already exists. Use --force to load anyway: {e}")
        except Exception as e:
            if not isinstance(e, CommandError):
                e.args = (f"Problem loading data '{archive.path}': {e}",)
            raise

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
