import logging

import polib

from .utils import get_hash


class POTranslationFile:
    """Translation file in PO format."""

    logger = logging.getLogger('file_formats')

    def __init__(self, logger=None):
        self.logger = logger
        self.file_path = None
        self.po_file = None

    def load(self, file_path):
        self.file_path = file_path
        self.po_file = polib.pofile(file_path)
        return self

    def get_untranslated_entries(self):
        return [
            message_obj for message_obj in self.po_file
            if not message_obj.translated() and not message_obj.msgid_plural
        ]

    def get_plural_untranslated_entries(self):
        return [
            message_obj for message_obj in self.po_file
            if message_obj.msgid_plural and not message_obj.translated()
        ]

    def get_translated_entries(self):
        return [
            message_obj for message_obj in self.po_file
            if message_obj.translated() and not message_obj.msgid_plural
        ]

    @staticmethod
    def build_translation_map(entries):
        """Builds a map of hash to translation object which are instances of type polib.POEntry."""
        translation_map = {}
        for message_obj in entries:
            key = get_hash(message_obj.msgid)
            if key in translation_map:
                if translation_map[key].msgid == message_obj.msgid:
                    POTranslationFile.logger.warning("Found duplicate key for the same message")
                    POTranslationFile.logger.warning(
                        f"{message_obj} | {translation_map[key]}"
                    )
                else:
                    POTranslationFile.logger.warning(
                        f"""Key {key} for {message_obj.msgid} already exists in translation map
                        for message '{translation_map[key].msgid}'
                        Existing object: {message_obj}
                        Current object: {translation_map[key]}"""
                    )
                continue

            translation_map[key] = message_obj
        return translation_map

    def add_translations(self, translations, translation_map):
        """Add translations to the pofile object. This does not save translations to the file."""
        for key, translated_str in translations.items():
            po_translation_obj = translation_map.get(key, None)
            if po_translation_obj:
                po_translation_obj.msgstr = translated_str
            else:
                # In few cases, the LLMs return a hash that is slightly different from the original hash
                # In this case, we will just skip the translation.
                # We will try to re-run the script again to get around with this issue.
                self.logger.warning(f"Translation object not found for key: {key} | {translated_str}")

    def add_plural_translations(self, translations, translation_map):
        """Add plural translations to the file. This does not save translations to the file."""
        for key, translated_dict in translations.items():
            po_translation_obj = translation_map.get(key, None)
            if po_translation_obj and 'singular' in translated_dict and 'plural' in translated_dict:
                po_translation_obj.msgstr_plural = {
                    '0': translated_dict['singular'],
                    '1': translated_dict['plural']
                }
            elif po_translation_obj:
                self.logger.warning(f"Invalid plural translation format for key: {key} {translated_dict}")
            else:
                self.logger.warning(f"Plural translation object not found for key: {key}")

    def save(self):
        """Save translations to the file."""
        self.po_file.save(self.file_path)
        self.logger.info(f"Saved translations to {self.file_path}")

    def compile(self):
        """Compile the PO file to MO format."""
        mo_file_path = self.file_path.replace('.po', '.mo')
        self.po_file.save_as_mofile(mo_file_path)
        self.logger.info(f"Compiled MO file saved at: {mo_file_path}")
