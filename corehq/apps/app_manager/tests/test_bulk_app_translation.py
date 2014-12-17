import codecs
import json
import os

from django.test import SimpleTestCase
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.tests.util import TestFileMixin
from corehq.apps.app_manager.translations import \
    process_bulk_app_translation_upload


class BulkAppTranslationTestBase(SimpleTestCase, TestFileMixin):

    def setUp(self):
        """
        Instantiate an app from file_path + app.json
        """
        super(BulkAppTranslationTestBase, self).setUp()
        self.app = app = Application.wrap(self.get_json("app"))

    def do_upload(self, name, expected_messages=None):
        """
        Upload the bulk app translation file at file_path + upload.xlsx
        """
        if not expected_messages:
            expected_messages = ["App Translations Updated!"]

        with codecs.open(self.get_path(name, "xlsx")) as f:
            messages = process_bulk_app_translation_upload(self.app, f)

        self.assertListEqual(
            [m[1] for m in messages], expected_messages
        )

    def assert_question_label(self, text, module_id, form_id, language, question_path):
        """
        assert that the given text is equal to the label of the given question.
        Return the label of the given question
        :param text:
        :param module_id: module index
        :param form_id: form index
        :param question_path: path to question (including "/data/")
        :return: the label of the question
        """
        form = self.app.get_module(module_id).get_form(form_id)
        labels = {}
        for lang in self.app.langs:
            for question in form.get_questions(
                    [lang], include_triggers=True, include_groups=True):
                labels[(question['value'], lang)] = question['label']

        self.assertEqual(
            labels[(question_path, language)],
            text
        )


class BulkAppTranslationBasicTest(BulkAppTranslationTestBase):

    file_path = "data", "bulk_app_translation", "basic"

    def test_set_up(self):
        self.assert_question_label("question1", 0, 0, "en", "/data/question1")

    def test_no_change_upload(self):
        self.do_upload("upload_no_change")
        self.assert_question_label("question1", 0, 0, "en", "/data/question1")

    def test_change_upload(self):
        self.do_upload("upload")

        self.assert_question_label("in english", 0, 0, "en", "/data/question1")
        self.assert_question_label("in french", 0, 0, "fra", "/data/question1")

        module = self.app.get_module(0)
        self.assertEqual(
            module.case_details.long.columns[1].enum[0].value['fra'],
            'french bar'
        )
        self.assertEqual(
            module.case_details.short.columns[0].header['fra'],
            'Nom'
        )


class MismatchedItextReferenceTest(BulkAppTranslationTestBase):
    """
    Test the bulk app translation upload when the itext reference in a question
    in the xform body does not match the question's id/path.

    The upload is an unchanged download.
    """
    file_path = "data", "bulk_app_translation", "mismatched_ref"

    def test_unchanged_upload(self):
        self.do_upload("upload")
        self.assert_question_label("question2", 0, 0, "en", "/data/foo/question2")


class BulkAppTranslationFormTest(BulkAppTranslationTestBase):

    file_path = "data", "bulk_app_translation", "form_modifications"

    def test_removing_form_translations(self):
        self.do_upload("modifications")
        form = self.app.get_module(0).get_form(0)
        self.assertXmlEqual(self.get_xml("expected_form"), form.render_xform())
