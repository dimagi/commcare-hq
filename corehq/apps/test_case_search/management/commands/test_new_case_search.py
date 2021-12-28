from django.core.management import BaseCommand

from corehq.util.decorators import require_debug_true
from corehq.apps.test_case_search.administer import reset_test_index
from corehq.apps.test_case_search.queries import run_all_queries


class Command(BaseCommand):
    help = 'Test out prospective changes to the case search index'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', default=False,
                            help="Wipe and rebuild the index")
        parser.add_argument('--query', action='store_true', default=False,
                            help="Run the queries defined in ")

    @require_debug_true()
    def handle(self, **options):
        if not options['reset'] and not options['query']:
            print("Pass either `--reset` or `--query` if you want this to do anything")

        if options['reset']:
            print("Resetting test case search index")
            reset_test_index()

        if options['query']:
            print("Running all queries")
            run_all_queries()

        print("Done, have a good day!")
