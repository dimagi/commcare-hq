from django.test import SimpleTestCase
from corehq.apps.translations.tests.utils import custom_translations, CUSTOM_LANGUAGE

from django.utils import translation
from django.utils.safestring import mark_safe
from django.utils.translation import gettext, gettext_lazy

from ...utils.translation import format_html_lazy


class TestCustomTranslationsDecorator(SimpleTestCase):
    @custom_translations({'Hello World': 'Hello Mundo'})
    def test_does_not_change_default_translation(self):
        self.assertEqual(gettext('Hello World'), 'Hello World')

    @custom_translations({'Hello World': 'Hello Mundo'})
    def test_creates_translation_for_custom_language(self):
        with translation.override(CUSTOM_LANGUAGE):
            self.assertEqual(gettext('Hello World'), 'Hello Mundo')

    @custom_translations({
        'TranslationOne': 'TranslationUno',
        'TranslationTwo': 'TranslationDos'
    })
    def test_handles_multiple_translations(self):
        with translation.override(CUSTOM_LANGUAGE):
            self.assertEqual(gettext('TranslationOne'), 'TranslationUno')
            self.assertEqual(gettext('TranslationTwo'), 'TranslationDos')


class TestLazyMarkSafe(SimpleTestCase):
    @custom_translations({'Translate Me': 'Translated'})
    def test_lazy_translation(self):
        translation_promise = mark_safe(gettext_lazy('Translate Me'))

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated')


class TestLazyFormatHTML(SimpleTestCase):
    @custom_translations({'Translate Me': 'Translated'})
    def test_no_params(self):
        translation_promise = format_html_lazy(gettext_lazy('Translate Me'))

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated')

    @custom_translations({'Format {}': 'Translated {} Format'})
    def test_with_params(self):
        translation_promise = format_html_lazy(gettext_lazy('Format {}'), 'Success')

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated Success Format')

    @custom_translations({
        'Format {}': 'Translated {} Format',
        'Token': 'Success'
    })
    def test_with_translated_params(self):
        translation_promise = format_html_lazy(
            gettext_lazy('Format {}'),
            gettext_lazy('Token')
        )

        with translation.override(CUSTOM_LANGUAGE):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated Success Format')
