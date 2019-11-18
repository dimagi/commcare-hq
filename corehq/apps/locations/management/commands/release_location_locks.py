from django.core.cache import cache
from django.core.management import BaseCommand


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
            help="Domain to clear locks for",
        )

    def handle(self, domain, **options):
        key1 = 'import_locations_async-{domain}'.format(domain=domain)
        key2 = 'import_locations_async-task-status-{domain}'.format(domain=domain)
        cache.delete(key1)
        cache.delete(key2)
