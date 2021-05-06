from django.conf import settings
from django.core.management.base import BaseCommand

from dimagi.ext.couchdbkit import Document

from corehq.util.metrics import metrics_gauge


class Command(BaseCommand):
    help = (
        "Display a variety of code-quality metrics, optionally sending them to datadog. "
        "Other metrics are computed in scripts/report-code-metrics.sh"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--datadog',
            action='store_true',
            default=False,
            help='Record these metrics in datadog',
        )

    def handle(self, **options):
        self.datadog = options['datadog']
        self.show_couch_model_count()
        self.show_custom_modules()

    def show_couch_model_count(self):
        def all_subclasses(cls):
            return set(cls.__subclasses__()).union([
                s for c in cls.__subclasses__() for s in all_subclasses(c)
            ])
        model_count = len(all_subclasses(Document))
        self.stdout.write(f"CouchDB models count: {model_count}")
        if self.datadog:
            metrics_gauge("commcare.gtd.num_couch_models", model_count)

    def show_custom_modules(self):
        num_custom_modules = len(set(settings.DOMAIN_MODULE_MAP.values()))
        num_custom_domains = len(settings.DOMAIN_MODULE_MAP)
        self.stdout.write(f"Custom modules: {num_custom_modules}")
        self.stdout.write(f"Domains using custom code: {num_custom_domains}")
        if self.datadog:
            metrics_gauge("commcare.gtd.num_custom_modules", num_custom_modules)
            metrics_gauge("commcare.gtd.num_custom_domains", num_custom_domains)
