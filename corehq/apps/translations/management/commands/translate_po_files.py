import logging
import sys
from argparse import RawTextHelpFormatter

from django.core.management.base import BaseCommand

from corehq.apps.translations.integrations.llms.config import TranslationConfig
from corehq.apps.translations.integrations.llms.file_formats import (
    POTranslationFile,
)
from corehq.apps.translations.integrations.llms.translation_judge import (
    POTranslationJudge,
)
from corehq.apps.translations.integrations.llms.translation_providers import (
    TranslationProviderFactory,
)
from corehq.apps.translations.integrations.llms.translation_service import (
    TranslationService,
)


class Command(BaseCommand):
    help = """
    Translate PO files using LLM services.

    This command translates untranslated strings in PO files to the specified target language.
    It can also verify the quality of translations and mark problematic ones as fuzzy.

    Examples:
        python manage.py translate_po_files es --verify
        python manage.py translate_po_files fr --env prod --batch-size 30
        python manage.py translate_po_files de --file-path /path/to/custom/file.po
    """

    def create_parser(self, *args, **kwargs):
        parser = super(Command, self).create_parser(*args, **kwargs)
        parser.formatter_class = RawTextHelpFormatter
        return parser

    def add_arguments(self, parser):
        parser.add_argument(
            '--lang',
            type=str,
            required=True,
            help='Target language code (e.g., es, fr, de)'
        )

        parser.add_argument(
            '--env',
            default='dev',
            choices=['dev', 'prod'],
            help='Environment to use (dev or prod). Default: dev'
        )

        parser.add_argument(
            '--batch-size',
            type=int,
            default=TranslationConfig.DEFAULT_BATCH_SIZE,
            help=f'Number of strings to translate in each batch. Default: {TranslationConfig.DEFAULT_BATCH_SIZE}'
        )

        parser.add_argument(
            '--rate-limit',
            type=int,
            default=TranslationConfig.DEFAULT_RATE_LIMIT,
            help=f'Seconds to wait between API calls. Default: {TranslationConfig.DEFAULT_RATE_LIMIT}'
        )

        parser.add_argument(
            '--verify',
            action='store_true',
            help='Verify translations and mark problematic ones as fuzzy'
        )

        parser.add_argument(
            '--file-path',
            help='Path to a specific PO file to translate (instead of all files)'
        )

        # OpenAI specific options
        parser.add_argument(
            '--openai-api-key',
            help='OpenAI API key (overrides settings.OPENAI_API_KEY)'
        )

        parser.add_argument(
            '--openai-model',
            default=TranslationConfig.OPENAI_MODEL,
            help=f'OpenAI model to use. Default: {TranslationConfig.OPENAI_MODEL}'
        )

        # LM Studio specific options
        parser.add_argument(
            '--lm-studio-base-url',
            default=TranslationConfig.LM_STUDIO_BASE_URL,
            help=f'LM Studio base URL. Default: {TranslationConfig.LM_STUDIO_BASE_URL}'
        )

        parser.add_argument(
            '--lm-studio-model',
            default=TranslationConfig.LM_STUDIO_MODEL,
            help=f'LM Studio model to use. Default: {TranslationConfig.LM_STUDIO_MODEL}'
        )

    def handle(self, *args, **options):
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout)
            ]
        )
        logger = logging.getLogger('translation_command')

        config = TranslationConfig(
            options['lang'],
            env=options['env'],
            batch_size=options['batch_size'],
            rate_limit=options['rate_limit'],
            openai_api_key=options.get('openai_api_key'),
            openai_model=options['openai_model'],
            lm_studio_base_url=options['lm_studio_base_url'],
            lm_studio_model=options['lm_studio_model']
        )

        # Create provider
        provider_config = config.get_provider_config()
        provider = TranslationProviderFactory.create_provider(
            provider_config.pop('provider_type'),
            **provider_config
        )

        judge = None
        if options['verify']:
            judge = POTranslationJudge(provider, config, logger=logger)
            logger.info("Translation verification enabled")

        # Create translation service
        service = TranslationService(provider, config, logger=logger, judge=judge)

        # Translate files
        if options['file_path']:
            # Translate a specific file
            file_path = options['file_path']
            logger.info(f"Translating single file: {file_path}")
            try:
                translation_file = POTranslationFile(logger=logger).load(file_path)
                service.translate_file(translation_file, options['lang'])
                logger.info(f"Successfully translated {file_path}")
            except Exception as e:
                logger.error(f"Error translating file {file_path}: {e}")
                raise
        else:
            # Translate all files
            logger.info(f"Starting translation process for language: {options['lang']}")
            service.translate_all_files()
            logger.info(f"Translation process completed for language: {options['lang']}")

        # Print verification summary if applicable
        if judge:
            summary = judge.get_verification_summary()
            logger.info("Verification Summary:")
            logger.info(summary)
