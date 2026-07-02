"""
One-off experiment command to establish a baseline for the AI app
translations feature: for every current (editable) app in the system,
count the translatable strings and source-language words that a bulk AI
translation run would operate on, along with the domain and its
CommCare plan edition.

Outputs a CSV with one row per app. Designed to be resumable
(``--start-from-domain``) and safe to run against production: it only
reads data, processes one domain at a time, and writes results
incrementally.
"""
import csv
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
        parser.add_argument('output_file', help='Path to write the CSV to')
        parser.add_argument(
            '--start-from-domain',
            help='Skip domains that sort before this one (for resuming a '
                 'previous run; domains are processed in sorted order)',
        )
        parser.add_argument(
            '--include-inactive-domains',
            action='store_true',
            help='Also include inactive/paused domains (default: active only)',
        )

    def handle(self, output_file, **options):
        domain_names = sorted(Domain.get_all_names())
        start_from = options['start_from_domain']
        if start_from:
            domain_names = [d for d in domain_names if d >= start_from]

        with open(output_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if f.tell() == 0:
                writer.writerow(CSV_HEADERS)
            for i, domain_name in enumerate(domain_names):
                try:
                    self._process_domain(domain_name, writer, options)
                except Exception:
                    self.stderr.write(f"Error processing domain {domain_name}")
                    traceback.print_exc(file=sys.stderr)
                f.flush()
                if (i + 1) % 100 == 0:
                    self.stdout.write(f"Processed {i + 1}/{len(domain_names)} domains")

        self.stdout.write(self.style.SUCCESS(f"Done. Output written to {output_file}"))

    def _process_domain(self, domain_name, writer, options):
        domain_obj = Domain.get_by_name(domain_name)
        if domain_obj is None:
            return
        if not domain_obj.is_active and not options['include_inactive_domains']:
            return

        apps = get_apps_in_domain(domain_name, include_remote=False)
        if not apps:
            return

        plan_edition = self._get_plan_edition(domain_name)
        for app in apps:
            writer.writerow(self._app_row(domain_name, plan_edition, app))

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
