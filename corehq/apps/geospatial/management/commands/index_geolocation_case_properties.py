from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Index geopoint data in ES'

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('--case_type', required=False)
        parser.add_argument('--query_limit', required=False)
        parser.add_argument('--chunk_size', required=False)

    def handle(self, *args, **options):
        domain = options['domain']
        case_type = options.get('case_type')
        query_limit = options.get('query_limit')
        chunk_size = options.get('chunk_size')
