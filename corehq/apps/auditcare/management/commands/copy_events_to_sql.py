from django.core.management.base import BaseCommand

from corehq.apps.auditcare.tasks import copy_events_to_sql
from corehq.apps.auditcare.utils.export import get_sql_start_date


class Command(BaseCommand):
    help = """Copy audit data from couch to sql"""

    def add_arguments(self, parser):
        parser.add_argument('limit', help="Number of records to copy")

    def handle(self, limit, **options):
        print(f"Initial sql start date {get_sql_start_date()}")
        count = copy_events_to_sql(int(limit))
        print(f"Updated {count} records")
        print(f"Final sql start date {get_sql_start_date()}")
