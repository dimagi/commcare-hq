from contextlib import ContextDecorator
from unittest.mock import MagicMock, patch
from django.test import SimpleTestCase

from django.utils import translation
from django.utils.translation import ugettext_lazy
from django.utils.translation.trans_real import translation as get_translations

from ...utils.translation import mark_safe_lazy, format_html_lazy

CUSTOM_LANGUAGE = 'custom'


class custom_translations(ContextDecorator):
    """
    A decorator/context manager to provide runtime translations for the 'custom' language
    """
    def __init__(self, translation_mapping):
        self.translation_mapping = translation_mapping

    def __enter__(self):
        translations = get_translations(CUSTOM_LANGUAGE)
        old_gettext = translations.gettext

        def lookup(id):
            return self.translation_mapping.get(id) or old_gettext(id)

        self.patcher = patch.object(translations, 'gettext', MagicMock(side_effect=lookup))
        self.patcher.start()

    def __exit__(self, exc_type, exc_value, traceback):
        self.patcher.stop()


class TestLazyMarkSafe(SimpleTestCase):
    @custom_translations({'Translate Me': 'Translated'})
    def test_lazy_translation(self):
        translation_promise = mark_safe_lazy(ugettext_lazy('Translate Me'))

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated')


class TestLazyFormatHTML(SimpleTestCase):
    @custom_translations({'Translate Me': 'Translated'})
    def test_no_params(self):
        translation_promise = format_html_lazy(ugettext_lazy('Translate Me'))

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated')

    @custom_translations({'Format {}': 'Translated {} Format'})
    def test_with_params(self):
        translation_promise = format_html_lazy(ugettext_lazy('Format {}'), 'Success')

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated Success Format')

    @custom_translations({
        'Format {}': 'Translated {} Format',
        'Token': 'Success'
    })
    def test_with_translated_params(self):
        translation_promise = format_html_lazy(
            ugettext_lazy('Format {}'),
            ugettext_lazy('Token')
        )

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated Success Format')
