"""
One-off experiment command to establish a baseline for the AI app
translations feature: for every current (editable) app in the system,
count the translatable strings and source-language words that a bulk AI
translation run would operate on, along with the domain and its
CommCare plan edition.

Outputs a CSV with one row per app. Designed to be resumable and safe to run against production: it only
reads data, processes one domain at a time, and writes results
incrementally.
"""
import csv
import os
import sys
import traceback

from django.core.management.base import BaseCommand

from corehq.apps.accounting.models import Subscription
from corehq.apps.app_manager.dbaccessors import get_apps_in_domain
from corehq.apps.domain.models import Domain
from corehq.apps.translations.app_translations.download import (
    get_bulk_app_sheets_by_name,
)
from corehq.apps.translations.app_translations.utils import (
    get_bulk_app_sheet_headers,
)

CSV_HEADERS = [
    'domain',
    'plan_edition',
    'app_id',
    'app_name',
    'default_lang',
    'langs',
    'num_langs',
    'string_count',
    'word_count',
    'error',
]


class Command(BaseCommand):
    help = ("Count translatable strings and words in every current app, "
            "with domain and plan, and write the result to a CSV.")

    def add_arguments(self, parser):
        parser.add_argument('output_file', help='Path to write the CSV to',
                            default='/home/cchq/app_string_count/app_translation_baseline.csv'
        )
        parser.add_argument(
            '--domains',
            help='Comma-separated list of domain names to process, instead '
                 'of every domain in the system. Bypasses --start-from-domain '
                 'and the automatic resume-from-output_file behavior; '
                 'per-app dedup against output_file still applies.',
        )

    def handle(self, output_file, **options):
        written_app_ids, last_domain = self._get_resume_state(output_file)

        if options['domains']:
            domain_names = sorted(
                d.strip() for d in options['domains'].split(',') if d.strip()
            )
        else:
            domain_names = sorted(Domain.get_all_names())
            start_from = last_domain
            if start_from:
                domain_names = [d for d in domain_names if d >= start_from]

        with open(output_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(CSV_HEADERS)
            for i, domain_name in enumerate(domain_names):
                try:
                    self._process_domain(domain_name, writer, options, written_app_ids)
                except Exception:
                    self.stderr.write(f"Error processing domain {domain_name}")
                    traceback.print_exc(file=sys.stderr)
                f.flush()
                if (i + 1) % 100 == 0:
                    self.stdout.write(f"Processed {i + 1}/{len(domain_names)} domains")

        self.stdout.write(self.style.SUCCESS(f"Done. Output written to {output_file}"))

    @staticmethod
    def _get_resume_state(output_file):
        """
        Reads any rows already written by a previous (possibly interrupted)
        run, so apps that were already processed can be skipped and
        processing can pick back up from the last domain reached. Domains
        are written in sorted order, so the last domain seen is the
        furthest point reached by the previous run.
        """
        if not os.path.exists(output_file):
            return set(), None

        with open(output_file, newline='') as f:
            reader = csv.reader(f)
            try:
                header = next(reader)
            except StopIteration:
                return set(), None
            domain_index = header.index('domain')
            app_id_index = header.index('app_id')

            written_app_ids = set()
            last_domain = None
            for row in reader:
                if len(row) <= max(domain_index, app_id_index):
                    continue
                written_app_ids.add(row[app_id_index])
                last_domain = row[domain_index]
            return written_app_ids, last_domain

    def _process_domain(self, domain_name, writer, options, written_app_ids):
        domain_obj = Domain.get_by_name(domain_name)
        if domain_obj is None:
            return

        apps = get_apps_in_domain(domain_name, include_remote=False)
        if not apps:
            return

        plan_edition = self._get_plan_edition(domain_name)
        for app in apps:
            if app.get_id in written_app_ids:
                continue
            writer.writerow(self._app_row(domain_name, plan_edition, app))
            written_app_ids.add(app.get_id)

    @staticmethod
    def _get_plan_edition(domain_name):
        subscription = Subscription.get_active_subscription_by_domain(domain_name)
        if subscription:
            return subscription.plan_version.plan.edition
        return 'Community'

    def _app_row(self, domain_name, plan_edition, app):
        base_row = [
            domain_name,
            plan_edition,
            app.get_id,
            app.name,
            app.default_language,
            ' '.join(app.langs),
            len(app.langs),
        ]
        try:
            string_count, word_count = count_app_strings(app)
        except Exception as e:
            return base_row + ['', '', f'{type(e).__name__}: {e}']
        return base_row + [string_count, word_count, '']


def count_app_strings(app, lang=None):
    """
    Count the non-empty source-language strings (and their words) that a
    bulk app translation of ``app`` would cover.

    Uses the same extraction as the bulk app translation download, so the
    counts match what an AI translation run would send to the LLM.
    """
    lang = lang or app.default_language
    headers_by_sheet = dict(get_bulk_app_sheet_headers(app, lang=lang))
    sheets = get_bulk_app_sheets_by_name(app, lang=lang)

    string_count = 0
    word_count = 0
    for sheet_name, rows in sheets.items():
        headers = list(headers_by_sheet.get(sheet_name, ()))
        try:
            lang_index = headers.index(f'default_{lang}')
        except ValueError:
            continue
        for row in rows:
            if len(row) <= lang_index:
                continue
            text = row[lang_index]
            if text:
                string_count += 1
                word_count += len(str(text).split())
    return string_count, word_count
