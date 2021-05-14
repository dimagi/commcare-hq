import os
import subprocess
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand

from datadog import api, initialize

from dimagi.ext.couchdbkit import Document

from corehq.toggles import all_toggles
from corehq.feature_previews import all_previews


class DatadogLogger:
    def __init__(self, stdout, datadog):
        self.stdout = stdout
        self.datadog = datadog
        if self.datadog:
            api_key = os.environ.get("DATADOG_API_KEY")
            app_key = os.environ.get("DATADOG_APP_KEY")
            assert api_key and app_key, "DATADOG_API_KEY and DATADOG_APP_KEY must both be set"
            initialize(api_key=api_key, app_key=app_key)
            self.metrics = []

    def log(self, metric, value, tags=None):
        self.stdout.write(f"{metric}: {value} {tags or ''}")
        if self.datadog:
            self.metrics.append({
                'metric': metric,
                'points': value,
                'type': "gauge",
                'host': "travis-ci.org",
                'tags': [
                    "environment:travis",
                    f"travis_build:{os.environ.get('TRAVIS_BUILD_ID')}",
                    f"travis_number:{os.environ.get('TRAVIS_BUILD_NUMBER')}",
                    f"travis_job_number:{os.environ.get('TRAVIS_JOB_NUMBER')}",
                ] + (tags or []),
            })

    def send_all(self):
        if self.datadog:
            api.Metric.send(self.metrics)
            self.metrics = []


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
        self.show_js_dependencies()
        self.show_toggles()
        self.logger.send_all()

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

    def show_js_dependencies(self):
        proc = subprocess.Popen(["./scripts/codechecks/hqDefine.sh", "static-analysis"], stdout=subprocess.PIPE)
        output = proc.communicate()[0].strip().decode("utf-8")
        (hqdefine_todo, hqdefine_done, requirejs_todo, requirejs_done) = output.split(" ")

        self.logger.log("commcare.static_analysis.hqdefine_file_count", int(hqdefine_todo), tags=[
            'status:todo',
        ])
        self.logger.log("commcare.static_analysis.hqdefine_file_count", int(hqdefine_done), tags=[
            'status:done',
        ])
        self.logger.log("commcare.static_analysis.requirejs_file_count", int(requirejs_todo), tags=[
            'status:todo',
        ])
        self.logger.log("commcare.static_analysis.requirejs_file_count", int(requirejs_done), tags=[
            'status:done',
        ])

    def show_toggles(self):
        counts = Counter(t.tag.name for t in all_toggles() + all_previews())
        for tag, count in counts.items():
            self.logger.log("commcare.static_analysis.toggle_count", count, [f"toggle_tag:{tag}"])
