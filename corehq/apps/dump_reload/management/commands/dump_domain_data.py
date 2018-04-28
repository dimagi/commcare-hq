from __future__ import absolute_import

import os
import sys
import gzip
import zipfile

from django.core.management.base import (
    BaseCommand,
    CommandError,
)
from django.conf import settings

from datetime import datetime
from collections import Counter

from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.apps.dump_reload.const import DATETIME_FORMAT
from corehq.apps.dump_reload.couch import CouchDataDumper
from corehq.apps.dump_reload.couch.dump import ToggleDumper, DomainDumper
from corehq.apps.dump_reload.sql import SqlDataDumper
from corehq.blobs.zipdb import get_export_filename
from corehq.blobs.migrate import EXPORTERS as BLOB_EXPORTERS

COUCH_DATA_DUMPERS = ['domain', 'couch', 'toggles']
SQL_DATA_DUMPERS = ['sql']
DATA_DUMPERS = COUCH_DATA_DUMPERS + SQL_DATA_DUMPERS
EXPORTERS = ['applications', 'multimedia', 'couch_xforms',
             'sql_xforms', 'saved_exports', 'demo_user_restores']

BLOB_EXPORT_USAGE = """Usage: ./manage.py run_blob_export [options] <slug> <domain>

Slugs:

{}

""".format('\n'.join(sorted(EXPORTERS)))


class Command(BaseCommand):
    """
    Single place to support taking data dumps for a domain from various databases.
    It's recommended to always run this in a tmux session because
    the dumping process can take quite long for domains with large amounts of data
    This is also supported via commcare-cloud
    commcare-cloud softlayer django-manage dump_domain_data enikshay --tmux

    You can also run things in parallel by running commands with different options like
    1. ./manage.py dump_domain_data enikshay --db sql
    2. ./manage.py dump_domain_data enikshay --db couch
    3. ./manage.py dump_domain_data enikshay --db riak
    or even break this down further by doing
    1. ./manage.py dump_domain_data enikshay --db couch --dumper domain --dumper toggles
    2. ./manage.py dump_domain_data enikshay --db couch --dumper couch
    3. ./manage.py dump_domain_data enikshay --db riak --exporter applications
    4. ./manage.py dump_domain_data enikshay --db riak --exporter saved_exports --exporter multimedia
    5. ./manage.py dump_domain_data enikshay --db riak --exporter sql_xforms --limit-to-db p1
    """

    def add_arguments(self, parser):
        parser.add_argument('domain_name')
        parser.add_argument(
            '--db',
            choices=['pg', 'couch', 'riak'],
            default='all'
        )
        parser.add_argument(
            '--exclude', dest='exclude', action='append', default=[],
            help='An app_label or app_label.ModelName to exclude '
                 '(use multiple --exclude to exclude multiple apps/models).'
        )
        parser.add_argument(
            '--console', action='store_true', default=False, dest='console',
            help='Write output to the console instead of to file.'
        )
        parser.add_argument('--dumper', dest='dumpers', action='append', default=[],
                            help='Dumper slug to run (use multiple --dumper to run multiple dumpers).')
        parser.add_argument('--exporter', dest='exporters', action='append', default=[],
                            help='Exporter slug to run '
                                 '(use multiple --slug to run multiple exporters or --all to run them all).')
        parser.add_argument('--chunk-size', type=int, default=100,
                            help='Maximum number of records to read from couch at once.')
        parser.add_argument('--limit-to-db', dest='limit_to_db',
                            help="When specifying a SQL importer for exporter sql-xforms use this to restrict "
                                 "the exporter to a single partition.")

    def ensure_args_for_pg(self, options):
        dumpers = options.get('dumpers')
        if dumpers:
            for dumper in dumpers:
                if dumper not in SQL_DATA_DUMPERS:
                    raise CommandError("Supported Dumpers for pg: {dumpers}".format(
                        dumpers=','.join(SQL_DATA_DUMPERS)
                    ))

    def ensure_args_for_couch(self, options):
        dumpers = options.get('dumpers')
        if dumpers:
            for dumper in dumpers:
                if dumper not in COUCH_DATA_DUMPERS:
                    raise CommandError("Supported Dumpers for couch: {dumpers}".format(
                        dumpers=','.join(COUCH_DATA_DUMPERS)
                    ))

    def ensure_args_for_riak(self, options):
        exporters = options.get('exporters')
        if exporters:
            for exporter in exporters:
                if exporter not in EXPORTERS:
                    raise CommandError("Supported Exporters for riak: {exporters}".format(
                        exporters=','.join(EXPORTERS)
                    ))

    def run_blob_export(self, domain_name, options):
        limit_to_db = options.get('limit_to_db')
        exporters = options['exporters']
        chunk_size = options['chunk_size']
        migrator_options = {}
        if limit_to_db:
            migrator_options['limit_to_db'] = limit_to_db

        for exporter_slug in exporters:
            try:
                exporter = BLOB_EXPORTERS[exporter_slug]
            except KeyError:
                raise CommandError(BLOB_EXPORT_USAGE)

            self.stdout.write("\nRunning exporter: {}\n{}".format(exporter_slug, '-' * 50))
            export_filename = get_export_filename(exporter_slug, domain_name)
            if os.path.exists(export_filename):
                reset_export = False
                self.stderr.write(
                    "WARNING: export file for {} exists. "
                    "Resuming export progress. Delete file to reset progress.".format(exporter_slug)
                )
            else:
                reset_export = True  # always reset if the file doesn't already exist
            exporter.by_domain(domain_name)
            total, skips = exporter.migrate(reset=reset_export, chunk_size=chunk_size, **migrator_options)
            if skips:
                sys.exit(skips)

    def dump_domain_data(self, domain_name, options):
        excludes = options.get('exclude')
        console = options.get('console')
        show_traceback = options.get('traceback')

        utcnow = datetime.utcnow().strftime(DATETIME_FORMAT)
        zipname = 'data-dump-{}-{}.zip'.format(domain_name, utcnow)

        self.stdout.ending = None
        stats = Counter()
        # domain dumper should be first since it validates domain exists
        data_dumpers = [DomainDumper, SqlDataDumper, CouchDataDumper, ToggleDumper]
        requested_dumpers = options.get('dumpers')
        use_data_dumpers = [dumper for dumper in data_dumpers if dumper.slug in requested_dumpers]

        for dumper in use_data_dumpers:
            filename = _get_dump_stream_filename(dumper.slug, domain_name, utcnow)
            stream = self.stdout if console else gzip.open(filename, 'wb')
            try:
                stats += dumper(domain_name, excludes).dump(stream)
            except Exception as e:
                if show_traceback:
                    raise
                raise CommandError("Unable to serialize database: %s" % e)
            finally:
                if stream:
                    stream.close()

            if not console:
                with zipfile.ZipFile(zipname, mode='a', allowZip64=True) as z:
                    z.write(filename, '{}.gz'.format(dumper.slug))

                os.remove(filename)

        self.stdout.ending = '\n'
        self.stdout.write('{0} Dump Stats {0}'.format('-' * 32))
        for model in sorted(stats):
            self.stdout.write("{:<50}: {}".format(model, stats[model]))
        self.stdout.write('{0}{0}'.format('-' * 38))
        self.stdout.write('Dumped {} objects'.format(sum(stats.values())))
        self.stdout.write('{0}{0}'.format('-' * 38))

        self.stdout.write('\nData dumped to file: {}'.format(zipname))

    def handle(self, domain_name, **options):
        db = options.get('db')
        if db == 'pg':
            if options.get('dumpers'):
                self.ensure_args_for_pg(options)
            else:
                options['dumpers'] = SQL_DATA_DUMPERS
            self.dump_domain_data(domain_name, options)
        elif db == 'couch':
            if options.get('dumpers'):
                self.ensure_args_for_couch(options)
            else:
                options['dumpers'] = COUCH_DATA_DUMPERS
            self.dump_domain_data(domain_name, options)
        elif db == 'riak':
            limit_to_db = options.get('limit_to_db')
            if limit_to_db:
                if settings.USE_PARTITIONED_DATABASE:
                    partitions = get_db_aliases_for_partitioned_query()
                    if limit_to_db not in partitions:
                        raise CommandError("Available paritions {partitions}".format(
                            partitions=','.join(partitions)
                        ))
                else:
                    raise CommandError("DB partition not supported in this environment")

            if options.get('exporters'):
                self.ensure_args_for_riak(options)
            else:
                options['exporters'] = EXPORTERS
            self.run_blob_export(domain_name, options)
        elif db == 'all':
            _options = options
            _options['dumpers'] = DATA_DUMPERS
            self.dump_domain_data(domain_name, _options)
            _options = options
            _options['exporters'] = EXPORTERS
            self.run_blob_export(domain_name, options)


def _get_dump_stream_filename(slug, domain, utcnow):
    return 'dump-{}-{}-{}.gz'.format(slug, domain, utcnow)
