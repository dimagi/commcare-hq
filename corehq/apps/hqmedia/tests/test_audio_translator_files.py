import uuid

from django.test import TestCase

from corehq.apps.app_manager.tests.app_factory import AppFactory
from corehq.apps.app_manager.tests.util import TestXmlMixin
from corehq.apps.hqmedia.models import CommCareAudio
from corehq.apps.hqmedia.view_helpers import download_audio_translator_files


class AudioTranslatorFilesTest(TestCase, TestXmlMixin):
    file_path = ('data',)

    def _get_app(self):
        factory = AppFactory(build_version='2.40.0')
        app = factory.app
        app.langs = ['en', 'fra']

        module, form = factory.new_basic_module('register', 'case')

        '''
            This form has two text questions, one with French audio present and one with it missing.

            It then has three select questions, each with two choices that share text and all
            have French audio specified. One set of choices has audio present for both, one has
            it missing for both, and one has it present for one choice and missing for the other.

            Lastly, it has two select questions, each with three choices that all have different
            text but use the same audio path. One of these two audio files is missing.
        '''
        form.source = self.get_xml('duplicate_text_questions').decode('utf-8')
        for path in form.wrapped_xform().audio_references():
            if 'present' in path or 'one_of_each1' in path:
                app.create_mapping(CommCareAudio(_id=uuid.uuid4().hex), path, save=False)

        return app

    def _worksheet_data(self, workbook, sheet_index):
        return [[col.value for col in row] for row in list(workbook.worksheets[sheet_index].iter_rows())]

    def test_create_files(self):
        app = self._get_app()

        files = download_audio_translator_files(app.domain, app, 'fra')
        translator_workbook = files['excel_for_translator.xlsx']
        bulk_upload_workbook = files['bulk_upload.xlsx']

        # Translator sheet should contain rows for the files that need to be recorded
        # - the text question with missing audio
        # - the select question where both choices are missing audio.
        # - each of the three choices for different_text_same_missing_audio
        self.assertEqual(2, len(translator_workbook.worksheets))
        rows = self._worksheet_data(translator_workbook, 0)
        self.assertEqual(6, len(rows))
        self.assertEqual(rows[0], ['fra', 'audio'])
        self.assertEqual(rows[1][0], 'This question has an audio file that is missing.')
        self.assertIn('missing_audio', rows[1][1])
        self.assertEqual(rows[2][0], 'choices_both_missing')
        self.assertIn('choices_both_missing', rows[2][1])
        choices_both_missing_path = rows[2][1]
        self.assertEqual(rows[3][0], 'different_text_same_missing_audio')
        self.assertIn('different_text_same_missing_audio', rows[3][1])
        self.assertEqual(rows[4][0], 'different_text_same_missing_audio2')
        self.assertRegex(rows[4][1], 'different_text_same_missing_audio1.*_2.mp3$')
        self.assertEqual(rows[5][0], 'different_text_same_missing_audio3')
        self.assertRegex(rows[5][1], 'different_text_same_missing_audio1.*_3.mp3$')

        # Upload sheet should rename one of each of the choice pairs, which have different paths but the same text,
        # and two of the three choices that have different text but shared the same missing audio path
        rows = self._worksheet_data(bulk_upload_workbook, 0)
        self.assertEqual(6, len(rows))
        headers = rows[0]
        text_index = headers.index('default_fra')
        audio_index = headers.index('audio_fra')

        # Order of rows in this file is non-deterministic, so test based on a text => audio path dict
        audio_by_text = {row[text_index]: row[audio_index] for row in rows[1:]}

        # For the question with two choices with the same text, each with an audio file, one of those choices
        # should get renamed to share the other one's path, but it doesn't matter which one.
        self.assertIn('choices_both_present', audio_by_text['choices_both_present'])

        # Verify that the path being used for the select question with both choices missing
        # is the same path that the translator is being asked to use in the other file.
        self.assertEqual(audio_by_text['choices_both_missing'], choices_both_missing_path)

        # Verify that the path being used for the select question with one audio missing
        # is the path that already exists in the application.
        choices_one_of_each_path = [key for key in app.multimedia_map.keys() if 'choices_one_of_each' in key][0]
        self.assertEqual(audio_by_text['choices_one_of_each'], choices_one_of_each_path)

        # Verify the new paths, created due to different text sharing the same audio path
        self.assertRegex(audio_by_text['different_text_same_missing_audio2'],
                         'different_text_same_missing_audio1.*_2.mp3$')
        self.assertRegex(audio_by_text['different_text_same_missing_audio3'],
                         'different_text_same_missing_audio1.*_3.mp3$')
