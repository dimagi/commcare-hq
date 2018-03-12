from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals
from corehq.form_processor.models import CommCareCaseSQL
from corehq.messaging.tasks import sync_case_for_messaging
from corehq.sql_db.util import get_db_aliases_for_partitioned_query
from corehq.util.log import with_progress_bar
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Sync messaging models for cases"

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('case_type')
        parser.add_argument('--start-from-db', dest='start_from_db')

    def handle(self, domain, case_type, start_from_db=None, **options):
        print("Resyncing messaging models for %s/%s ..." % (domain, case_type))

        db_aliases = get_db_aliases_for_partitioned_query()
        db_aliases.sort()
        if start_from_db:
            if start_from_db not in db_aliases:
                raise CommandError("DB alias not recognized: %s" % start_from_db)

            index = db_aliases.index(start_from_db)
            db_aliases = db_aliases[index:]

        print("Iterating over databases: %s" % db_aliases)

        for db_alias in db_aliases:
            print("")
            print("Creating tasks for cases in %s ..." % db_alias)
            case_ids = list(
                CommCareCaseSQL
                .objects
                .using(db_alias)
                .filter(domain=domain, type=case_type, deleted=False)
                .values_list('case_id', flat=True)
            )
            for case_id in with_progress_bar(case_ids):
                sync_case_for_messaging.delay(domain, case_id)
