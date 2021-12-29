from django.core.management import BaseCommand

from corehq.util.decorators import require_debug_true
from corehq.apps.test_case_search.administer import reset_test_index, load_domain
from corehq.apps.test_case_search.queries import run_all_queries


class Command(BaseCommand):
    help = 'Test out prospective changes to the case search index'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', default=False,
                            help="Wipe and rebuild the index")
        parser.add_argument('--load-domain', help="Load a domain's cases into this index")
        parser.add_argument('--query', action='store_true', default=False,
                            help="Run the queries defined in ")

    @require_debug_true()
    def handle(self, **options):
        arg_options = ['reset', 'load_domain', 'query']
        if not any(options[param] for param in arg_options):
            print("Pass at least one of {} if you want this to do anything".format(
                ', '.join(f"--{option}" for option in arg_options)
            ))

        if options['reset']:
            print("Resetting test case search index")
            reset_test_index()

        domain = options['load_domain']
        if domain:
            print(f"loading domain '{domain}'")
            load_domain(domain)

        if options['query']:
            print("Running all queries")
            run_all_queries()

        print("Done, have a good day!")
