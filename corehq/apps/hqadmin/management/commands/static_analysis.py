import os
import re
import subprocess
from collections import Counter, namedtuple
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand

import datadog
from github import Github

from dimagi.ext.couchdbkit import Document
from dimagi.utils.chunked import chunked

from corehq.feature_previews import all_previews
from corehq.toggles import all_toggles

Metric = namedtuple('Metric', "name value tags")


def to_querystring(metric):
    tag = ",".join(metric.tags).replace(" ", "_").lower() or "*"
    return f"avg:{metric.name}{{{tag}}}"


def _normalize_number(value):
    if value == int(value):
        return int(value)
    return round(value, 3)


class AnalysisLogger:
    def __init__(self, stdout):
        self.stdout = stdout
        self.metrics = []

        self.pull_request = None
        if os.environ.get('TRAVIS_PULL_REQUEST', 'false') != 'false':
            self.pr_number = int(os.environ['TRAVIS_PULL_REQUEST'])
            assert os.environ.get('DIMAGIMON_GITHUB_TOKEN') is not None, \
                "DIMAGIMON_GITHUB_TOKEN must be set"
            gh = Github(os.environ['DIMAGIMON_GITHUB_TOKEN'])
            repo = gh.get_repo('dimagi/commcare-hq')
            self.pull_request = repo.get_pull(self.pr_number)

        self.submit_to_datadog = os.environ.get('TRAVIS_EVENT_TYPE') == 'cron'
        if self.submit_to_datadog or self.pull_request:
            api_key = os.environ.get("DATADOG_API_KEY")
            app_key = os.environ.get("DATADOG_APP_KEY")
            assert api_key and app_key, "DATADOG_API_KEY and DATADOG_APP_KEY must both be set"
            datadog.initialize(api_key=api_key, app_key=app_key)

    def log(self, name, value, tags=None):
        self.stdout.write(f"{name}: {value} {tags or ''}")
        self.metrics.append(Metric(name, value, tags or []))

    def send_all(self):
        self._send_to_datadog()
        self._send_to_github()

    def _send_to_datadog(self):
        if not self.submit_to_datadog:
            self.stdout.write("This isn't the daily travis build, not submitting to datadog")
            return

        datadog.api.Metric.send([
            {
                'metric': metric.name,
                'points': metric.value,
                'type': "gauge",
                'host': "travis-ci.org",
                'tags': [
                    "environment:travis",
                    f"travis_build:{os.environ.get('TRAVIS_BUILD_ID')}",
                    f"travis_number:{os.environ.get('TRAVIS_BUILD_NUMBER')}",
                    f"travis_job_number:{os.environ.get('TRAVIS_JOB_NUMBER')}",
                ] + metric.tags,
            } for metric in self.metrics
        ])
        self.stdout.write("Analysis sent to datadog")

    def _send_to_github(self):
        if not self.pull_request:
            self.stdout.write("No PR detected, not submitting info to github")
            return

        previous_values = self._fetch_previous_values()

        comment_lines = [
            "### Code Analysis\n",
            "Metric name | tags | old value | new value",
            "------------|------|-----------|----------",
        ]
        for metric in self.metrics:
            comment_lines.append(" | ".join([
                metric.name,
                ", ".join(metric.tags),
                str(previous_values.get(to_querystring(metric), "")),
                str(metric.value),
            ]))

        self.pull_request.create_issue_comment("\n".join(comment_lines))
        self.stdout.write(f"Analysis submitted to github PR {self.pr_number}")

    def _fetch_previous_values(self):
        """Lookup latest values that have been saved to datadog"""
        previous_values = {}
        for metrics in chunked(self.metrics, 10):
            query = ",".join(to_querystring(metric) for metric in metrics)
            res = datadog.api.Metric.query(
                start=(datetime.now() - timedelta(days=2)).timestamp(),
                end=datetime.now().timestamp(),
                query=query,
            )
            if 'error' in res:
                raise Exception(res['error'])
            previous_values.update(
                (d['expression'], _normalize_number(d['pointlist'][-1][-1]))
                for d in res['series']
            )
        return previous_values


class Command(BaseCommand):
    help = "Display a variety of code-quality metrics."

    def handle(self, **options):
        self.logger = AnalysisLogger(self.stdout)
        self.show_couch_model_count()
        self.show_custom_modules()
        self.show_js_dependencies()
        self.show_toggles()
        self.show_complexity()
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
        (step1, step2, step3) = output.split(" ")

        self.logger.log("commcare.static_analysis.hqdefine_file_count", int(step1), tags=[
            'status:unmigrated',
        ])
        self.logger.log("commcare.static_analysis.hqdefine_file_count", int(step2), tags=[
            'status:hqdefine_only',
        ])
        self.logger.log("commcare.static_analysis.requirejs_file_count", int(step3), tags=[
            'status:migrated',
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
