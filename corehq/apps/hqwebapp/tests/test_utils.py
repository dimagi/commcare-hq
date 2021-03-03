from django.test import SimpleTestCase

from django.utils.translation import (
    ugettext_lazy,
    override
)

from ..utils import mark_safe_lazy, format_html_lazy


def given_translation(id, message):
    # Translations are set up in locale/test/LC_MESSAGES/django.po
    # Modify that file and then run `django-admin compilemessages -l test`
    # if you want to test other translations.

    # The expected translations these tests work against are:
    # - 'Translate Me' -> 'Translated Test'
    # - 'Translate Format {}' -> 'Test Translate Translated Format {}'
    pass  # No-op.


class TestLazyTranslations(SimpleTestCase):
    def test_lazy_translation(self):
        given_translation('Translate Me', 'Translated Test')

        translation_promise = mark_safe_lazy(ugettext_lazy('Translate Me'))
        with override('test'):
            translation = str(translation_promise)

        self.assertEqual(translation, 'Translated Test')


class TestLazyFormatHTML(SimpleTestCase):
    def test_no_params(self):
        given_translation('Translate Me', 'Translated Test')

        translation_promise = format_html_lazy(ugettext_lazy('Translate Me'))
        with override('test'):
            translated = str(translation_promise)

        self.assertEqual(translated, 'Translated Test')

    def test_with_params(self):
        given_translation('Translate Format {}', 'Test Translated Format {}')

        translation_promise = format_html_lazy(ugettext_lazy('Translate Format {}'), 'Success')

        with override('test'):
            translation = str(translation_promise)

        self.assertEqual(translation, 'Test Translated Format Success')

    def test_with_translated_params(self):
        given_translation('Translate Format {}', 'Test Translated Format {}')
        given_translation('Translate Me', 'Translated Test')

        translation_promise = format_html_lazy(
            ugettext_lazy('Translate Format {}'),
            ugettext_lazy('Translate Me')
        )

        with override('test'):
            translation = str(translation_promise)

        self.assertEqual(translation, 'Test Translated Format Translated Test')
