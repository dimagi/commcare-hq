from contextlib import ContextDecorator
from unittest.mock import patch

from django.utils.translation.trans_real import translation as get_translations

CUSTOM_LANGUAGE = 'custom'


class custom_translations(ContextDecorator):
    """
    A decorator/context manager to provide runtime translations for the 'custom' language.
    Decorate your method with something like:
    @custom_translations({'original': 'translated'})

    and then within the test you can use:
    with translation.override(CUSTOM_LANGUAGE):
       gettext('original')
    """
    def __init__(self, translation_mapping):
        self.translation_mapping = translation_mapping

    def __enter__(self):
        translations = get_translations(CUSTOM_LANGUAGE)
        old_gettext = translations.gettext

        def lookup(id):
            return self.translation_mapping.get(id) or old_gettext(id)

        self.patcher = patch.object(translations, 'gettext', lookup)
        self.patcher.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.patcher.stop()
