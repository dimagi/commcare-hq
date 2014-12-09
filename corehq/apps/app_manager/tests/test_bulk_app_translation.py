import codecs
import json
import os

from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestFileMixin
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


class BulkAppTranslationFormTest(SimpleTestCase, TestFileMixin):

    # Note:
    # This test seeks to demonstrate that the bulk app translator behaves the
    # same way as the bulk form translator in vellum on STAGING at the moment
    # (9257af38c646cf91575ded602d4a20e16959b7da).
    # Vellum's bulk app translator on prod seems to not know how to handle
    # deleted translations at the moment.
    #
    # There is one difference in the behavior:
    # - Bulk app translator allows for empty <text> nodes, and will not remove
    #   a <text> node if all <value> (translation) nodes are removed from it.

    file_path = "data", "bulk_app_translation", "form_modifications"

    def test_removing_form_translations(self):
        app = Application.wrap(self.get_json("app"))
        with codecs.open(self.get_path("modifications", "xlsx")) as f:
            process_bulk_app_translation_upload(app, f)
        form = app.get_module(0).get_form(0)
        self.assertXmlEqual(self.get_xml("expected_form"), form.render_xform())
