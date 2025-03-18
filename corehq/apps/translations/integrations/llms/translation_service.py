import logging
from copy import deepcopy
from time import time

import gevent
from gevent import sleep

from corehq.apps.translations.integrations.llms.file_formats import (
    POTranslationFile,
)


class TranslationService:
    """Service for translating files. This service is there to act as a glue
    between File Formats and Translation Provider.

    It also contains the logic for batching and rate limiting.
    """

    def __init__(self, provider, config, logger=None, judge=None):
        self.provider = provider
        self.config = config
        self.logger = logger or logging.getLogger('translation_service')
        self.judge = judge

    def translate_file(self, translation_file, target_lang):
        """Translate a single file.

        Args:
            translation_file: The file to translate
            target_lang: The language to translate to
        """
        self.logger.info(f"Translating {translation_file.file_path}")
        start_time = time()

        untranslated_entries = translation_file.get_untranslated_entries()
        self.logger.info(f"Total translations to process: {len(untranslated_entries)}")

        if untranslated_entries:
            translation_map = translation_file.build_translation_map(untranslated_entries)
            batches = self.create_batches(translation_map)
            translated_strings = self.process_batches(
                batches, target_lang, translation_map
            )
            translation_file.add_translations(translated_strings, translation_map)
            if self.judge:
                self.judge.verify_translations_entries(
                    untranslated_entries, target_lang, deepcopy(translation_map))
            translation_file.save()

        plural_entries = translation_file.get_plural_untranslated_entries()
        self.logger.info(f"Total plural translations to process: {len(plural_entries)}")

        if plural_entries:
            plural_translation_map = translation_file.build_translation_map(plural_entries)
            plural_batches = self.create_plural_batches(plural_translation_map)
            plural_translated_strings = self.process_batches(
                plural_batches, target_lang, plural_translation_map, is_plural=True
            )
            translation_file.add_plural_translations(plural_translated_strings, plural_translation_map)
            translation_file.save()

        translation_file.compile()

        end_time = time()
        self.logger.info(f"File translated in {(end_time - start_time)/60:.2f} minutes")

    def translate_all_files(self):
        """Translate all files specified in the configuration."""
        self.logger.info(f"Starting translation process for language: {self.config.language}")
        start_time = time()

        for file_path in self.config.get_po_file_paths():
            try:
                translation_file = POTranslationFile(logger=self.logger).load(file_path)
                self.translate_file(translation_file, self.config.language)
            except Exception as e:
                self.logger.error(f"Error translating file {file_path}", e)
        end_time = time()
        self.logger.info(f"Total time taken: {(end_time - start_time)/60:.2f} minutes for {self.config.language}")

    def create_batches(self, translation_map):
        """
        Create batches from a translation map.

        Args:
            translation_map: Map of hash to translation object

        Returns:
            List of batches
        """
        dict_keys = list(translation_map.keys())
        batches = []
        for i in range(0, len(dict_keys), self.config.batch_size):
            batch_keys = dict_keys[i:i + self.config.batch_size]
            batches.append([{key: translation_map[key].msgid} for key in batch_keys])
        return batches

    def create_plural_batches(self, translation_map):
        """
        Create plural batches from a translation map.

        Args:
            translation_map: Map of hash to translation object

        Returns:
            List of batches
        """
        dict_keys = list(translation_map.keys())
        batches = []
        for i in range(0, len(dict_keys), self.config.batch_size):
            batch_keys = dict_keys[i:i + self.config.batch_size]
            batch = []
            for key in batch_keys:
                batch.append({
                    key: {
                        'singular': translation_map[key].msgid,
                        'plural': translation_map[key].msgid_plural
                    }
                })
            batches.append(batch)
        return batches

    def process_batches(self, batches, target_lang, translation_map, is_plural=False):
        """
        Process batches of translations.

        Args:
            batches: List of batches to process
            target_lang: Target language code
            translation_map: Map of hash to translation object
            is_plural: Whether to use plural translation

        Returns:
            Dict of translations
        """
        translation_calls = []
        for batch in batches:
            if is_plural:
                translation_calls.append(
                    gevent.spawn(self.provider.translate_plural_batch, batch, target_lang)
                )
            else:
                translation_calls.append(
                    gevent.spawn(self.provider.translate_batch, batch, target_lang)
                )
            sleep(self.config.rate_limit)  # Added for rate limiting

        gevent.joinall(translation_calls)
        results = [call.value for call in translation_calls]

        translations = {}
        for result in results:
            translations.update(result)
        return translations
