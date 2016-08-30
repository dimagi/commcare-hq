from django.core.management.base import LabelCommand, CommandError

from corehq.apps.couch_sql_migration.couchsqlmigration import do_couch_to_sql_migration
from corehq.form_processor.utils import should_use_sql_backend


class Command(LabelCommand):

    def handle_label(self, domain, **options):
        if should_use_sql_backend(domain):
            raise CommandError(u'It looks like {} has already been migrated.'.format(domain))

        do_couch_to_sql_migration(domain)
