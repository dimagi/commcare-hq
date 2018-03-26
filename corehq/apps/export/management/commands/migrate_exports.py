from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
import traceback

from django.core.management.base import BaseCommand

from corehq.apps.export.utils import migrate_domain
from corehq.apps.domain.models import Domain
from corehq.form_processor.utils.general import use_new_exports
from corehq.util.log import send_HTML_email


class Command(BaseCommand):
    help = "Migrates old exports to new ones"

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            dest='dryrun',
            default=False,
            help='Runs a dry run on the export conversations',
        )
        parser.add_argument(
            '--limit',
            dest='limit',
            default=None,
            type=int,
            help='Limits the number of domains migrated',
        )
        parser.add_argument(
            '--force-convert-columns',
            action='store_true',
            dest='force_convert_columns',
            default=False,
            help='Force convert columns that were not found in the new schema',
        )

    def handle(self, **options):
        dryrun = options.pop('dryrun')
        limit = options.pop('limit')
        force_convert_columns = options.pop('force_convert_columns')
        count = 0

        if dryrun:
            print('*** Running in dryrun mode. Will not save any conversion ***')

        print('*** Migrating {} exports ***'.format(limit or 'ALL'))
        skipped_domains = []

        for doc in Domain.get_all(include_docs=False):
            domain = doc['key']

            if not use_new_exports(domain):
                if not force_convert_columns:
                    try:
                        metas = migrate_domain(domain, dryrun=True, force_convert_columns=force_convert_columns)
                    except Exception:
                        print('Migration raised an exception, skipping.')
                        traceback.print_exc()
                        skipped_domains.append(domain)
                        continue

                    has_skipped_tables = any([bool(meta.skipped_tables) for meta in metas])
                    has_skipped_columns = any([bool(meta.skipped_columns) for meta in metas])
                    is_remote_app_migration = any([bool(meta.is_remote_app_migration) for meta in metas])
                    if has_skipped_tables or has_skipped_columns:
                        print('Skipping {} because we would have skipped columns'.format(domain))
                        skipped_domains.append(domain)
                        continue

                    if is_remote_app_migration:
                        print('Skipping {} because it contains remote apps'.format(domain))
                        skipped_domains.append(domain)
                        continue

                if not dryrun:
                    print('Migrating {}'.format(domain))
                    try:
                        migrate_domain(domain, dryrun=False, force_convert_columns=force_convert_columns)
                    except Exception:
                        print('Migration raised an exception, skipping.')
                        skipped_domains.append(domain)
                        continue
                else:
                    print('No skipped tables/columns. Not migrating since dryrun is specified')
                count += 1
            if limit is not None and count >= limit:
                break

        send_HTML_email(
            'Export migration results',
            '{}@{}'.format('commcarehq-ops+admins', 'dimagi.com'),

            '''
            Skipped domains: {} <br />
            Successfully migrated: {}
            '''.format(
                ', '.join(skipped_domains),
                count,
            )
        )
