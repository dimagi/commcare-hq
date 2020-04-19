from django.core.management import BaseCommand

from corehq.apps.change_feed import topics


class Command(BaseCommand):

    def handle(self, **options):
        print('\n'.join(topics.ALL))
