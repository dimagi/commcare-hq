import codecs
import json
import os

from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.translations import \
    process_bulk_app_translation_upload


class BulkAppTranslationTest(SimpleTestCase):

    @classmethod
    def setUpClass(cls):
        with codecs.open(os.path.join(
                os.path.dirname(__file__), "data", "bulk_translate_app.json"
        ), encoding='utf-8') as f:

            cls.app = Application.wrap(json.load(f))

    def test_set_up(self):
        form = self.app.get_module(0).get_form(0)

        labels = {}
        for lang in self.app.langs:
            for question in form.get_questions(
                    [lang], include_triggers=True, include_groups=True):
                labels[(question['value'], lang)] = question['label']

        self.assertEqual(labels["/data/question1", "en"], "question1")

    def test_no_change_upload(self):
        with codecs.open(os.path.join(
                os.path.dirname(__file__), "data",
                "bulk_app_translations_no_change.xlsx")) as f:
            messages = process_bulk_app_translation_upload(self.app, f)

        self.assertListEqual(
            [m[1] for m in messages], ["App Translations Updated!"]
        )

    def test_upload(self):
        with codecs.open(os.path.join(
                os.path.dirname(__file__), "data",
                "bulk_app_translations.xlsx")) as f:
            messages = process_bulk_app_translation_upload(self.app, f)
            self.assertListEqual(
                [m[1] for m in messages],
                ["App Translations Updated!"]
            )

        form = self.app.get_module(0).get_form(0)

        labels = {}
        for lang in self.app.langs:
            for question in form.get_questions(
                    [lang], include_triggers=True, include_groups=True):
                labels[(question['value'], lang)] = question['label']

        self.assertEqual(labels[("/data/question1", "en")], "in english")
        self.assertEqual(labels[("/data/question1", "fra")], "in french")

        module = self.app.get_module(0)
        self.assertEqual(
            module.case_details.long.columns[1].enum[0].value['fra'],
            'french bar'
        )
        self.assertEqual(
            module.case_details.short.columns[0].header['fra'],
            'Nom'
        )
