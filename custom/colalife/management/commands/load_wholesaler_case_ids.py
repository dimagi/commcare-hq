from django.core.management import BaseCommand


class Command(BaseCommand):
    help = 'Assign wholesaler case IDs to child cases.'

    def handle(self, *args, **options):
        pass
