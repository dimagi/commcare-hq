"""CLI entry point for AI app translation (see ai_translator.py)."""
from django.core.management.base import BaseCommand, CommandError

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.translations.app_translations.ai_translator import (
    AppTranslationFormat,
    run_app_translation,
)
from corehq.apps.translations.const import (
    AI_TRANSLATION_CHUNK_SIZE,
    MODE_FILL_MISSING,
    MODE_RETRANSLATE,
)


class Command(BaseCommand):
    help = "Translate an app's content into a target language using an LLM."

    def add_arguments(self, parser):
        parser.add_argument('domain')
        parser.add_argument('app_id')
        parser.add_argument('lang', help='Target language code (e.g. fra)')
        parser.add_argument('--mode', choices=[MODE_FILL_MISSING, MODE_RETRANSLATE],
                            default=MODE_FILL_MISSING)
        parser.add_argument('--model', help='LLM model override')
        parser.add_argument('--chunk-size', type=int, default=AI_TRANSLATION_CHUNK_SIZE)
        parser.add_argument('--dry-run', action='store_true',
                            help='Extract and report counts; no LLM calls, no writes')

    def handle(self, domain, app_id, lang, **options):
        app = get_app(domain, app_id)
        if lang not in app.langs:
            raise CommandError(f"App does not have language '{lang}'")
        if lang == app.default_language:
            raise CommandError("Target language is the app's default language")

        if options['dry_run']:
            fmt = AppTranslationFormat(app, lang, mode=options['mode'])
            units = fmt.load_input()
            words = sum(len(u.source_text.split()) for u in units.values())
            self.stdout.write(f"Would translate {len(units)} strings ({words} words)")
            return

        summary = run_app_translation(
            app, lang, options['mode'], model=options['model'],
            chunk_size=options['chunk_size'],
            progress_callback=lambda done, total: self.stdout.write(
                f"batch {done}/{total}"),
        )
        pct = (100 * summary['translated'] // summary['total']) if summary['total'] else 100
        self.stdout.write(self.style.SUCCESS(
            f"{summary['translated']} of {summary['total']} strings translated ({pct}%), "
            f"{summary['skipped']} skipped, {summary['failed']} failed"))
        for error in summary['errors']:
            self.stderr.write(error)
