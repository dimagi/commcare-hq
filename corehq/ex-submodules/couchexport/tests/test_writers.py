# coding: utf-8
from codecs import BOM_UTF8

import StringIO

from couchexport.writers import ZippedExportWriter, CsvFileWriter, PythonDictWriter
from django.test import SimpleTestCase
from mock import patch, Mock


class ZippedExportWriterTests(SimpleTestCase):

    def setUp(self):
        self.zip_file_patch = patch('zipfile.ZipFile')
        self.MockZipFile = self.zip_file_patch.start()

        self.path_mock = Mock()
        self.path_mock.get_path.return_value = 'tmp'

        self.writer = ZippedExportWriter()
        self.writer.tables = [self.path_mock]
        self.writer.file = Mock()

    def tearDown(self):
        self.zip_file_patch.stop()
        del self.writer

    def test_zipped_export_writer_unicode(self):
        mock_zip_file = self.MockZipFile.return_value
        self.writer.table_names = {0: u'ひらがな'}
        self.writer._write_final_result()
        mock_zip_file.write.assert_called_with('tmp', 'ひらがな.csv')

    def test_zipped_export_writer_utf8(self):
        mock_zip_file = self.MockZipFile.return_value
        self.writer.table_names = {0: '\xe3\x81\xb2\xe3\x82\x89\xe3\x81\x8c\xe3\x81\xaa'}
        self.writer._write_final_result()
        mock_zip_file.write.assert_called_with('tmp', 'ひらがな.csv')


class CsvFileWriterTests(SimpleTestCase):

    def test_csv_file_writer_bom(self):
        """
        CsvFileWriter should prepend a byte-order mark to the start of the CSV file for Excel
        """
        writer = CsvFileWriter()
        headers = ['ham', 'spam', 'eggs']
        writer.open('Spam')
        writer.write_row(headers)
        writer.finish()
        file_start = writer.get_file().read(6)
        self.assertEqual(file_start, BOM_UTF8 + 'ham')


class HeaderNameTest(SimpleTestCase):

    def test_names_matching_case(self):
        writer = PythonDictWriter()
        stringio = StringIO.StringIO()
        table_index_1 = "case_Sensitive"
        table_index_2 = "case_sensitive"
        table_headers = [[]]
        writer.open(
            [
                (table_index_1, table_headers),
                (table_index_2, table_headers)
            ],
            stringio
        )
        writer.close()
        preview = writer.get_preview()

        first_sheet_name = preview[0]['table_name']
        second_sheet_name = preview[1]['table_name']
        self.assertNotEqual(
            first_sheet_name.lower(),
            second_sheet_name.lower(),
            "Sheet names must not be equal. Comparison is NOT case sensitive. Names were '{}' and '{}'".format(
                first_sheet_name, second_sheet_name
            )
        )

    def test_max_header_length(self):
        writer = PythonDictWriter()
        writer.max_table_name_size = 10
        stringio = StringIO.StringIO()
        table_index = "my_table_index"
        table_headers = [("first header", "second header")]
        writer.open(
            [(table_index, table_headers)],
            stringio
        )
        writer.close()
        preview = writer.get_preview()
        self.assertGreater(len(table_index), writer.max_table_name_size)
        self.assertLessEqual(len(preview[0]['table_name']), writer.max_table_name_size)


