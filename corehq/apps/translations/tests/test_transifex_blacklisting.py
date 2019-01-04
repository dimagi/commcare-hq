from __future__ import absolute_import
from __future__ import unicode_literals

from django.test import TestCase
from mock import patch, Mock

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.translations.generators import AppTranslationsGenerator


class PropertyMock(Mock):
    def __get__(self, instance, owner):
        return self()


class TestTransifexBlacklist(TestCase, TestXmlMixin):
    file_path = ('..', '..', 'translations', 'tests', 'data', )

    @classmethod
    def setUpClass(cls):
        super(TestTransifexBlacklist, cls).setUpClass()
        factory = AppFactory()
        app = factory.app
        app.langs = ['en', 'hin']
        module, form = factory.new_basic_module('register', 'case')
        form.source = cls.get_xml('transifex_blacklist').decode('utf-8')

        with patch('corehq.apps.translations.generators.AppTranslationsGenerator.app',
                   new_callable=PropertyMock) as mock:
            mock.return_value = app
            trans_gen = AppTranslationsGenerator(
                'domain', 'app_id', 1, 'en', 'en', 'default_'
            )
            translations = trans_gen.translations

        first_form_translations = translations['form_register_form_0_v1']
        cls.labels_sent_to_transifex = [
            trans.msgctxt for trans in first_form_translations
        ]

    def test_allowed_label(self):
        self.assertIn('information-label', self.labels_sent_to_transifex)

    def test_allowed_validation_message(self):
        self.assertIn('validation_message-label', self.labels_sent_to_transifex)
        self.assertIn('validation_message-constraintMsg', self.labels_sent_to_transifex)

    def test_blacklisted_validation_message(self):
        self.assertNotIn('sample_text_question-label', self.labels_sent_to_transifex)
        self.assertNotIn('sample_text_question-constraintMsg', self.labels_sent_to_transifex)

    def test_allowed_help_message(self):
        self.assertIn('information-help', self.labels_sent_to_transifex)

    def test_allowed_hint_message(self):
        self.assertIn('information-hint', self.labels_sent_to_transifex)

    def test_blacklisted_choices(self):
        self.assertNotIn('sample_choice_question-label', self.labels_sent_to_transifex)
        self.assertNotIn('sample_choice_question-choice1-label', self.labels_sent_to_transifex)
        self.assertNotIn('sample_choice_question-choice2-label', self.labels_sent_to_transifex)
        self.assertIn('sample_choice_question-choice3-label', self.labels_sent_to_transifex)

    def test_choice_with_duplicate_label(self):
        self.assertIn('test_choice_with_same_label_itext-label', self.labels_sent_to_transifex)
        self.assertIn('sample_choice_question-choice3-label', self.labels_sent_to_transifex)
