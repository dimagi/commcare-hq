from django.core.management.base import BaseCommand

from dimagi.ext.couchdbkit import Document

from corehq.util.metrics import metrics_gauge


class Command(BaseCommand):
    help = "Display a variety of code-quality metrics, optionally sending them to datadog"

    def add_arguments(self, parser):
        parser.add_argument(
            '--datadog',
            action='store_true',
            default=False,
            help='Record these metrics in datadog',
        )

    def handle(self, **options):
        self.datadog = options['datadog']
        self.show_couch_docs_remaining()

    def show_couch_docs_remaining(self):
        def all_subclasses(cls):
            return set(cls.__subclasses__()).union([
                s for c in cls.__subclasses__() for s in all_subclasses(c)
            ])
        num_remaining = len(all_subclasses(Document))
        self.stdout.write(f"CouchDB models remaining: {num_remaining}")
        if self.datadog:
            metrics_gauge("commcare.gtd.num_couch_models", num_remaining)
