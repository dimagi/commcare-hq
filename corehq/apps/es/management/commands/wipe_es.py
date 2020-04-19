from django.core.management import BaseCommand

from corehq.apps.cleanup.utils import confirm_destructive_operation
from corehq.elastic import get_es_new


class Command(BaseCommand):
    """
    Wipe all data from BlobDB.
    """
    def add_arguments(self, parser):
        parser.add_argument(
            '--commit',
            action='store_true',
            dest='commit',
            default=False,
        )

    def handle(self, *args, **options):
        confirm_destructive_operation()

        data = wipe_es(options['commit'])

        if data:
            print(data)
        if not options['commit']:
            print("You need to run with --commit for the deletion to happen.")


def wipe_es(commit=False):
    """
    The equivalent of calling ::

        $ curl -X DELETE "$PROTO://$HOSTNAME:$PORT/_all"
    """
    es = get_es_new()
    if commit:
        return es.transport.perform_request('DELETE', '_all')
