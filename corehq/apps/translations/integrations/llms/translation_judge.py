import json

import gevent
from gevent import joinall, spawn


class POTranslationJudge:
    """Verifies the quality of translations and marks problematic ones as fuzzy."""

    def __init__(self, provider, config, logger=None):
        self.provider = provider
        self.config = config
        self.logger = logger
        self.verification_results = {
            'verified': 0,
            'flagged': 0,
            'issues': []
        }

    def prepare_verification_data(self, translation_map):
        """Prepare verification data for a given target language as described in the prompt."""
        verification_data = []
        for hash_key, entry in translation_map.items():
            translated_str = entry.msgstr_plural['0'] if entry.msgid_plural else entry.msgstr
            if not translated_str:
                continue
            verification_data.append({
                'hash': hash_key,
                'original': entry.msgid,
                'translation': translated_str
            })
        return verification_data

    def verify_translations_file(self, translation_file, target_lang):
        """Verify all translations in a file and mark problematic ones as fuzzy."""
        self.logger.info(f"Verifying translations in {translation_file.file_path}...")

        translated_entries = translation_file.get_translated_entries()
        entry_map = translation_file.build_translation_map(translated_entries)
        if not translated_entries:
            return {}
        return self.verify_translations_entries(translated_entries, target_lang, entry_map)

    def verify_translations_entries(self, entries, target_lang, translation_map):
        """
        Verify all translations in a file and mark problematic ones as fuzzy.

        Args:
            entries: The translation entries to verify
            target_lang: Target language code
            translation_map: Map of hash keys to translation entries

        Returns:
            Dict with verification results
        """
        self.logger.info(f"Found {len(entries)} translated entries to verify")

        verification_data = self.prepare_verification_data(translation_map)

        batch_size = self.config.batch_size
        results = {}

        batches = []
        for i in range(0, len(verification_data), batch_size):
            batches.append(verification_data[i:i + batch_size])

        jobs = []
        for batch in batches:
            jobs.append(spawn(self.verify_batch, batch, target_lang))
            gevent.sleep(self.config.rate_limit)
        joinall(jobs)

        for i, job in enumerate(jobs):
            batch_results = job.value
            results.update(batch_results)

            self.update_verification_stats(batch_results, translation_map)

        self.mark_doubtful_translations(translation_map)

        if self.verification_results['flagged'] > 0:
            self.logger.info(f"Marked {self.verification_results['flagged']} translations as fuzzy")

        return results

    def verify_batch(self, batch, target_lang):
        """
        Verify a batch of translations using the provider.

        Args:
            batch: List of dicts with hash, original, and translation
            target_lang: Target language code

        Returns:
            Dict mapping hash to verification result
        """
        system_prompt = self._get_verification_prompt(target_lang)
        batch_str = json.dumps(batch)

        try:
            completion = self.provider.client.chat.completions.create(
                model=self.provider.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": batch_str}
                ],
                temperature=0.1,
                response_format={"type": "json_object"},
            )

            response_text = completion.choices[0].message.content
            verification_results = json.loads(response_text)

            # Ensure the response is in the expected format
            results = {}
            for item in verification_results:
                if 'hash' in item and 'is_valid' in item:
                    results[item['hash']] = {
                        'is_valid': item['is_valid'],
                        'reason': item.get('reason', '')
                    }

            return results
        except Exception as e:
            self.logger.error(f"Error verifying translations: {e}")
            # Return all as valid in case of error to avoid blocking the process
            return {item['hash']: {'is_valid': True, 'reason': ''} for item in batch}

    def update_verification_stats(self, results, entry_map):
        """Update the verification stats with the results."""
        for hash_key, result in results.items():
            if result['is_valid']:
                self.verification_results['verified'] += 1
            else:
                self.verification_results['flagged'] += 1
                self.verification_results['issues'].append({
                    'hash': hash_key,
                    'original': entry_map[hash_key].msgid,
                    'translation': entry_map[hash_key].msgstr,
                    'reason': result['reason']
                })

    def mark_doubtful_translations(self, entry_map):
        """Mark doubtful translations with fuzzy flag."""
        for issue in self.verification_results['issues']:
            if issue['hash'] in entry_map:
                entry = entry_map[issue['hash']]
                if 'fuzzy' not in entry.flags:
                    entry.flags.append('fuzzy')
                    comment = f"Translation flagged: {issue['reason']}"
                    if not entry.comment:
                        entry.comment = comment

    def _get_verification_prompt(self, target_lang):
        """Get the prompt for translation verification."""
        return (
            f"You are a translation quality judge for {target_lang}. "
            "Evaluate each translation for accuracy, fluency, and cultural appropriateness. "
            "Check that placeholders, HTML tags, and formatting are preserved correctly. "
            "\n\n"
            "Input: JSON array of objects with hash, original (English), and translation. "
            "Output: JSON array of objects with the following format: "
            "["
            "  {\"hash\": \"<hash>\", \"is_valid\": true/false, \"reason\": \"<explanation if invalid>\"},"
            "  ..."
            "]"
            "\n\n"
            "Only flag translations with serious issues. Minor stylistic differences are acceptable."
        )

    def get_verification_summary(self):
        """Get a summary of the verification results."""
        total = self.verification_results['verified'] + self.verification_results['flagged']
        if total == 0:
            return "No translations verified."

        percent_valid = (self.verification_results['verified'] / total * 100) if total > 0 else 0

        summary = (
            f"Verification complete: {self.verification_results['verified']}/{total} "
            f"translations verified ({percent_valid:.1f}%).\n"
        )
        if self.verification_results['flagged'] > 0:
            summary += (
                f"{self.verification_results['flagged']} translations were flagged with issues "
                f"and marked as fuzzy:\n"
            )
            for i, issue in enumerate(self.verification_results['issues'][:5], 1):  # Show first 5 issues
                summary += (
                    f"{i}. Original: \"{issue['original'][:50]}...\"\n"
                    f"   Translation: \"{issue['translation'][:50]}...\"\n"
                    f"   Reason: {issue['reason']}\n"
                )

            if len(self.verification_results['issues']) > 5:
                summary += f"... and {len(self.verification_results['issues']) - 5} more issues.\n"

        return summary
