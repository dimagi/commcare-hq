import os
import re
import subprocess
from collections import Counter

from django.conf import settings
from django.core.management.base import BaseCommand

import datadog

from dimagi.ext.couchdbkit import Document

from corehq.feature_previews import all_previews
from corehq.toggles import all_toggles


class DatadogLogger:
    def __init__(self, stdout):
        self.stdout = stdout
        self.datadog = (
            os.environ.get("TRAVIS_EVENT_TYPE") == 'cron'
            or os.environ.get("GITHUB_EVENT_NAME") == 'schedule'
        )
        if self.datadog:
            api_key = os.environ.get("DATADOG_API_KEY")
            app_key = os.environ.get("DATADOG_APP_KEY")
            assert api_key and app_key, "DATADOG_API_KEY and DATADOG_APP_KEY must both be set"
            datadog.initialize(api_key=api_key, app_key=app_key)
            self.metrics = []

    def log(self, metric, value, tags=None):
        self.stdout.write(f"{metric}: {value} {tags or ''}")
        if os.environ.get("GITHUB_ACTIONS"):
            env = "github_actions"
            host = "github.com"
        elif os.environ.get("TRAVIS"):
            env = "travis"
            host = "travis-ci.org"
        else:
            env = "unknown"
            host = "unknown"
        if self.datadog:
            self.metrics.append({
                'metric': metric,
                'points': value,
                'type': "gauge",
                'host': host,
                'tags': [f"environment:{env}"] + (tags or []),
            })

    def send_all(self):
        if self.datadog:
            datadog.api.Metric.send(self.metrics)
            self.metrics = []


class Command(BaseCommand):
    help = ("Display a variety of code-quality metrics. This is run on every CI "
            "build, but only submitted to datadog during the daily cron job.")

    def handle(self, **options):
        self.stdout.write("----------> Begin Static Analysis <----------")
        self.logger = DatadogLogger(self.stdout)
        self.show_couch_model_count()
        self.show_custom_modules()
        self.show_js_dependencies()
        self.show_toggles()
        self.show_complexity()
        self.logger.send_all()
        self.stdout.write("----------> End Static Analysis <----------")

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
        proc = subprocess.Popen(["./scripts/codechecks/amd.sh", "static-analysis"], stdout=subprocess.PIPE)
        output = proc.communicate()[0].strip().decode("utf-8")
        (step1, step2) = output.split(" ")

        self.logger.log("commcare.static_analysis.hqdefine_file_count", int(step1), tags=[
            'status:esm',
        ])
        self.logger.log("commcare.static_analysis.hqdefine_file_count", int(step2), tags=[
            'status:hqdefine',
        ])

    def show_toggles(self):
        counts = Counter(t.tag.name for t in all_toggles() + all_previews())
        for tag, count in counts.items():
            self.logger.log("commcare.static_analysis.toggle_count", count, [f"toggle_tag:{tag}"])

    def show_complexity(self):
        # We can use `--json` for more granularity, but it doesn't provide a summary
        output = subprocess.run([
            "radon", "cc", ".",
            "--min=C",
            "--total-average",
            "--exclude=node_modules/*,staticfiles/*",
        ], stdout=subprocess.PIPE).stdout.decode('utf-8').strip()
        raw_blocks, raw_complexity = output.split('\n')[-2:]

        blocks_pattern = r'^(\d+) blocks \(classes, functions, methods\) analyzed.$'
        blocks = int(re.match(blocks_pattern, raw_blocks).group(1))
        self.logger.log("commcare.static_analysis.code_blocks", blocks)

        complexity_pattern = r'^Average complexity: A \(([\d.]+)\)$'
        complexity = round(float(re.match(complexity_pattern, raw_complexity).group(1)), 3)
        self.logger.log("commcare.static_analysis.avg_complexity", complexity)

        for grade in ["C", "D", "E", "F"]:
            count = len(re.findall(f" - {grade}\n", output))
            self.logger.log(
                "commcare.static_analysis.complex_block_count",
                count,
                tags=[f"complexity_grade:{grade}"],
            )
