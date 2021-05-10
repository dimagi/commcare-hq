import os

from django.conf import settings
from django.core.management.base import BaseCommand

from datadog import api, initialize

from dimagi.ext.couchdbkit import Document


class Command(BaseCommand):
    help = (
        "Display a variety of code-quality metrics, optionally sending them to datadog. "
        "Other metrics are computed in scripts/static-analysis.sh"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--datadog',
            action='store_true',
            default=False,
            help='Record these metrics in datadog',
        )

    def handle(self, **options):
        self.logger = DatadogLogger(self.stdout, options['datadog'])
        self.show_couch_model_count()
        self.show_custom_modules()

    def show_couch_model_count(self):
        def all_subclasses(cls):
            return set(cls.__subclasses__()).union([
                s for c in cls.__subclasses__() for s in all_subclasses(c)
            ])
        model_count = len(all_subclasses(Document))
        self.logger.log("commcare.static_analysis.couch_model_count", model_count)

    def show_custom_modules(self):
        custom_module_count = len(set(settings.DOMAIN_MODULE_MAP.values()))
        custom_domain_count = len(settings.DOMAIN_MODULE_MAP)
        self.logger.log("commcare.static_analysis.custom_module_count", custom_module_count)
        self.logger.log("commcare.static_analysis.custom_domain_count", custom_domain_count)


class DatadogLogger:
    def __init__(self, stdout, datadog):
        self.stdout = stdout
        self.datadog = datadog
        if datadog:
            api_key = os.environ.get("DATADOG_API_KEY")
            app_key = os.environ.get("DATADOG_APP_KEY")
            assert api_key and app_key, "DATADOG_API_KEY and DATADOG_APP_KEY environment variables must both be set"
            initialize(api_key=api_key, app_key=app_key)

    def log(self, metric, value):
        self.stdout.write(f"{metric}: {value}")
        if not self.datadog:
            return

        api.Metric.send(
            metric=metric,
            points=value,
            type="gauge",
            host="travis-ci.org",
            tags=[
                "environment:travis",
                f"travis_build:{os.environ.get('TRAVIS_BUILD_ID')}",
                f"travis_number:{os.environ.get('TRAVIS_BUILD_NUMBER')}",
                f"travis_job_number:{os.environ.get('TRAVIS_JOB_NUMBER')}",
            ],
        )
