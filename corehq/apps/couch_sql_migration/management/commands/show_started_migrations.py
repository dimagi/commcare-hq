from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

from operator import attrgetter

import six
from django.core.management.base import BaseCommand

from corehq.apps.domain_migration_flags.api import get_uncompleted_migrations

from ...progress import COUCH_TO_SQL_SLUG


class Command(BaseCommand):
    """Show domains for which the migration has been strated and not completed"""

    def handle(self, **options):
        migrations = get_uncompleted_migrations(COUCH_TO_SQL_SLUG)
        for status, items in sorted(six.iteritems(migrations)):
            print(status)
            for item in sorted(items, key=attrgetter("domain")):
                started = item.started_on
                print("  {}{}".format(
                    item.domain,
                    started.strftime(" (%Y-%m-%d)") if started else "",
                ))
