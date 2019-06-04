from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from operator import attrgetter

from django.core.management.base import BaseCommand

import six

from corehq.apps.domain_migration_flags.api import get_uncompleted_migrations
from corehq.form_processor.utils import should_use_sql_backend

from ...progress import COUCH_TO_SQL_SLUG
from .migrate_multiple_domains_from_couch_to_sql import (
    format_diff_stats,
    get_diff_stats,
)


class Command(BaseCommand):
    """Show domains for which the migration has been strated and not completed"""

    def add_arguments(self, parser):
        parser.add_argument("--stats", action="store_true", dest="show_stats",
            help="Print migration statistics for each listed domain.")

    def handle(self, show_stats=False, **options):
        migrations = get_uncompleted_migrations(COUCH_TO_SQL_SLUG)
        for status, items in sorted(six.iteritems(migrations)):
            print(status)
            for item in sorted(items, key=attrgetter("domain")):
                started = item.started_on
                print("  {}{}".format(
                    item.domain,
                    started.strftime(" (%Y-%m-%d)") if started else "",
                ))
                if show_stats:
                    try:
                        stats = get_diff_stats(item.domain)
                        if stats:
                            stats = format_diff_stats(stats)
                            print("    " + stats.replace("\n", "\n    "))
                    except Exception as err:
                        print("    Cannot get diff stats: {}".format(err))
