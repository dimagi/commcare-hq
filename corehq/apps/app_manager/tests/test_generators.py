import os

from django.test.testcases import SimpleTestCase

import polib

from corehq.apps.translations.generators import PoFileGenerator, Translation

translations = [
    Translation('hello', 'नमस्ते', [('occurrence-hello', '')], '0:occurrence-hello'),
    Translation('bye', 'अलविदा', [('occurrence-bye', '')], '0:occurrence-bye'),
]


class TestPoFileGenerator(SimpleTestCase):
    def test_translations_in_generated_files(self):
        all_translations = {
            'sheet1': list(translations),
            'sheet2': list(translations),
        }
        file_paths = []
        with PoFileGenerator(all_translations, {}) as po_file_generator:
            generated_files = po_file_generator.generate_translation_files()
            for file_name, file_path in generated_files:
                file_paths.append(file_path)
                list_of_translations = polib.pofile(file_path)
                # assure translations
                self.assertEqual(list_of_translations[0].msgid, 'hello')
                self.assertEqual(list_of_translations[0].msgstr, 'नमस्ते')
                self.assertEqual(list_of_translations[0].msgctxt, '0:occurrence-hello')
                self.assertEqual(list_of_translations[0].occurrences, [('occurrence-hello', '')])
                self.assertEqual(list_of_translations[1].msgid, 'bye')
                self.assertEqual(list_of_translations[1].msgstr, 'अलविदा')
                self.assertEqual(list_of_translations[1].msgctxt, '0:occurrence-bye')
                self.assertEqual(list_of_translations[1].occurrences, [('occurrence-bye', '')])

        # assure files are cleaned
        for file_path in file_paths:
            self.assertFalse(os.path.exists(file_path))

    def test_metadata(self):
        all_translations = {'sheet1': list(translations)}
        metadata = {
            'MIME-Version': '1.0',
            'Content-Type': 'text/plain; charset=utf-8',
            'Language': 'hin',
        }
        with PoFileGenerator(all_translations, metadata) as po_file_generator:
            generated_files = po_file_generator.generate_translation_files()
            for file_name, file_path in generated_files:
                # ensure meta data
                with open(file_path, encoding='utf-8') as f:
                    file_content = f.read()
                    self.assertIn("Language: hin", file_content)
                    self.assertIn("MIME-Version: 1.0", file_content)
                    self.assertIn("Content-Type: text/plain; charset=utf-8", file_content)
