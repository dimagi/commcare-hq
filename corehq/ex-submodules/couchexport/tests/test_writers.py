# coding: utf-8
from __future__ import absolute_import
from __future__ import unicode_literals
from codecs import BOM_UTF8
from contextlib import closing
import io
import os
import six

from django.test import SimpleTestCase
from lxml import html, etree
from mock import patch, Mock

from couchexport.export import export_from_tables
from couchexport.models import Format
from couchexport.writers import (
    MAX_XLS_COLUMNS,
    CsvFileWriter,
    PythonDictWriter,
    XlsLengthException,
    ZippedExportWriter,
)
from six.moves import range


class ZippedExportWriterTests(SimpleTestCase):

    def setUp(self):
        self.zip_file_patch = patch('zipfile.ZipFile')
        self.MockZipFile = self.zip_file_patch.start()

        self.path_mock = Mock()
        self.path_mock.get_path.return_value = 'tmp'

        self.writer = ZippedExportWriter()
        self.writer.archive_basepath = '✓path'
        self.writer.tables = [self.path_mock]
        self.writer.file = Mock()

    def tearDown(self):
        self.zip_file_patch.stop()
        del self.writer

    def test_zipped_export_writer_unicode(self):
        mock_zip_file = self.MockZipFile.return_value
        self.writer.table_names = {0: 'ひらがな'}
        self.writer._write_final_result()
        filename = os.path.join(self.writer.archive_basepath, 'ひらがな.csv')
        if six.PY2:
            filename = filename.encode('utf-8')
        mock_zip_file.write.assert_called_with('tmp', filename)

    def test_zipped_export_writer_utf8(self):
        mock_zip_file = self.MockZipFile.return_value
        self.writer.table_names = {0: b'\xe3\x81\xb2\xe3\x82\x89\xe3\x81\x8c\xe3\x81\xaa'}
        self.writer._write_final_result()
        filename = os.path.join(self.writer.archive_basepath, 'ひらがな.csv')
        if six.PY2:
            filename = filename.encode('utf-8')
        mock_zip_file.write.assert_called_with('tmp', filename)


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
        self.assertEqual(file_start, BOM_UTF8 + b'ham')

    def test_csv_file_writer_utf8(self):
        writer = CsvFileWriter()
        headers = ['hám', 'spam', 'eggs']
        writer.open('Spam')
        writer.write_row(headers)
        writer.finish()
        file_start = writer.get_file().read(7)
        self.assertEqual(file_start, BOM_UTF8 + 'hám'.encode('utf-8'))

    def test_csv_file_writer_int(self):
        writer = CsvFileWriter()
        headers = [100, 'spam', 'eggs']
        writer.open('Spam')
        writer.write_row(headers)
        writer.finish()
        file_start = writer.get_file().read(6)
        self.assertEqual(file_start, BOM_UTF8 + b'100')


class HtmlExportWriterTests(SimpleTestCase):

    def test_nones_transformed(self):
        headers = ('Breakfast', 'Breakfast', 'Amuse-Bouche', 'Breakfast')
        row = ('spam', 'spam', None, 'spam')
        table = (headers, row, row, row)
        export_tables = (('Spam', table),)

        with closing(io.BytesIO()) as file_:
            export_from_tables(export_tables, file_, Format.HTML)
            html_string = file_.getvalue()

        root = html.fromstring(html_string)
        html_rows = [
            [etree.tostring(td).strip().decode('utf-8') for td in tr.xpath('./td')]
            for tr in root.xpath('./body/table/tbody/tr')
        ]
        self.assertEqual(html_rows,
                         [['<td>spam</td>', '<td>spam</td>', '<td/>', '<td>spam</td>'],
                          ['<td>spam</td>', '<td>spam</td>', '<td/>', '<td>spam</td>'],
                          ['<td>spam</td>', '<td>spam</td>', '<td/>', '<td>spam</td>']])


class Excel2007ExportWriterTests(SimpleTestCase):

    def test_bytestrings(self):
        format_ = Format.XLS_2007
        file_ = io.BytesIO()
        table = [
            [b'heading\xe2\x80\x931', b'heading\xe2\x80\x932', b'heading\xe2\x80\x933'],
            [b'row1\xe2\x80\x931', b'row1\xe2\x80\x932', b'row1\xe2\x80\x933'],
            [b'row2\xe2\x80\x931', b'row2\xe2\x80\x932', b'row2\xe2\x80\x933'],
        ]
        tables = [[b'table\xe2\x80\x93title', table]]
        export_from_tables(tables, file_, format_)


class Excel2003ExportWriterTests(SimpleTestCase):

    def test_data_length(self):
        format_ = Format.XLS
        file_ = io.BytesIO()
        table = [
            ['header{}'.format(i) for i in range(MAX_XLS_COLUMNS + 1)],
            ['row{}'.format(i) for i in range(MAX_XLS_COLUMNS + 1)],
        ]
        tables = [['title', table]]

        with self.assertRaises(XlsLengthException):
            export_from_tables(tables, file_, format_)

        table = [
            ['header{}'.format(i) for i in range(MAX_XLS_COLUMNS)],
            ['row{}'.format(i) for i in range(MAX_XLS_COLUMNS)],
        ]
        tables = [['title', table]]
        export_from_tables(tables, file_, format_)


class HeaderNameTest(SimpleTestCase):

    def test_names_matching_case(self):
        writer = PythonDictWriter()
        stringio = io.StringIO()
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
        stringio = io.StringIO()
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

    def test_max_header_length_duplicates(self):
        writer = PythonDictWriter()
        writer.max_table_name_size = 7
        stringio = io.StringIO()
        table_headers = [("header1", "header2")]
        writer.open(
            [
                ("prefix1: index", table_headers),
                ("prefix2- index", table_headers),
            ],
            stringio
        )
        writer.close()
        preview = writer.get_preview()
        table_names = {table['table_name'] for table in preview}
        self.assertEqual(len(table_names), 2)
