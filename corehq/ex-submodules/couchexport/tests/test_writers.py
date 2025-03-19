from codecs import BOM_UTF8
from contextlib import closing
import io
import os

from django.test import SimpleTestCase
from lxml import html, etree
from unittest.mock import patch, Mock

from couchexport.export import export_from_tables
from couchexport.models import Format
from couchexport.writers import (
    MAX_XLS_COLUMNS,
    CsvFileWriter,
    PythonDictWriter,
    XlsLengthException,
    ZippedExportWriter,
    GeoJSONWriter,
)
from corehq.apps.export.models import TableConfiguration
from corehq.apps.export.models import SplitGPSExportColumn, GeopointItem, PathNode


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
        mock_zip_file.write.assert_called_with('tmp', filename)

    def test_zipped_export_writer_utf8(self):
        mock_zip_file = self.MockZipFile.return_value
        self.writer.table_names = {0: b'\xe3\x81\xb2\xe3\x82\x89\xe3\x81\x8c\xe3\x81\xaa'}
        self.writer._write_final_result()
        filename = os.path.join(self.writer.archive_basepath, 'ひらがな.csv')
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
            [etree.tostring(td, encoding='utf-8').strip().decode('utf-8') for td in tr.xpath('./td')]
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

    def test_even_max_header_length(self):
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
        self.assertEqual(preview[0]['table_name'], "my_t...dex")
        self.assertLessEqual(len(preview[0]['table_name']), writer.max_table_name_size)

    def test_odd_max_header_length(self):
        writer = PythonDictWriter()
        writer.max_table_name_size = 15
        stringio = io.StringIO()
        table_index = "another sheet tab name"
        table_headers = [("header1", "header2")]
        writer.open(
            [(table_index, table_headers)],
            stringio
        )
        writer.close()
        preview = writer.get_preview()
        self.assertEqual(preview[0]['table_name'], "anothe...b name")
        self.assertLessEqual(len(preview[0]['table_name']), writer.max_table_name_size)

    def test_exact_max_header_length(self):
        writer = PythonDictWriter()
        writer.max_table_name_size = 19
        stringio = io.StringIO()
        table_index = "sheet_name_for_tabs"
        table_headers = [("header1", "header2")]
        writer.open(
            [(table_index, table_headers)],
            stringio
        )
        writer.close()
        preview = writer.get_preview()
        self.assertEqual(preview[0]['table_name'], "sheet_name_for_tabs")
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


class TestGeoJSONWriter(SimpleTestCase):
    GEO_PROPERTY = 'geo-prop'

    def test_get_features(self):
        table = TableConfiguration(selected_geo_property=self.GEO_PROPERTY)
        features = GeoJSONWriter().get_features(table, self._table_data())

        expected_features = [
            {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': ['-71.057083', '42.361145']},
                'properties': {'name': 'Boston', 'country': 'United States'}
            },
            {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': ['18.423300', '-33.918861']},
                'properties': {'name': 'Cape Town', 'country': 'South Africa'}
            },
            {
                'type': 'Feature',
                'geometry': {'type': 'Point', 'coordinates': ['77.2300', '28.6100']},
                'properties': {'name': 'Delhi', 'country': 'India'}
            },
        ]
        self.assertEqual(features, expected_features)

    def test_get_features__other_geo_property_configured(self):
        table = TableConfiguration(selected_geo_property="some-other-property")
        features = GeoJSONWriter().get_features(table, self._table_data())
        self.assertEqual(features, [])

    def test_get_features__invalid_geo_property_column_value(self):
        table = TableConfiguration(selected_geo_property=self.GEO_PROPERTY)

        data = self._table_data()
        data[1][1] = "not-a-geo-coordinate-value"
        features = GeoJSONWriter().get_features(table, data)

        features_names = [feature['properties']['name'] for feature in features]
        self.assertTrue(data[1][2] not in features_names)

    def test_get_features_from_path(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="some.path",
            path_string='some.path',
        )
        features = GeoJSONWriter().get_features(table, self._table_data(geo_property_header='some.path'))

        expected_features = [
            {
                'geometry': {'coordinates': ['-71.057083', '42.361145'], 'type': 'Point'},
                'properties': {'country': 'United States', 'name': 'Boston'},
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['18.423300', '-33.918861'], 'type': 'Point'},
                'properties': {'country': 'South Africa', 'name': 'Cape Town'},
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['77.2300', '28.6100'], 'type': 'Point'},
                'properties': {'country': 'India', 'name': 'Delhi'},
                'type': 'Feature'
            },
        ]
        self.assertEqual(features, expected_features)

    def test_get_features_from_path__invalid_path(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="some.other.path",
            path_string='some.path',
        )
        features = GeoJSONWriter().get_features(table, self._table_data(geo_property_header='some.path'))

        expected_features = []
        self.assertEqual(features, expected_features)

    def test_get_features_from_path__location_metadata(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="form.meta.location",
            path_string="form.meta.location",
            header_name='location',
        )
        features = GeoJSONWriter().get_features(table, self._table_data(geo_property_header='location'))

        expected_features = [
            {
                'geometry': {'coordinates': ['-71.057083', '42.361145'], 'type': 'Point'},
                'properties': {'country': 'United States', 'name': 'Boston'},
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['18.423300', '-33.918861'], 'type': 'Point'},
                'properties': {'country': 'South Africa', 'name': 'Cape Town'},
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['77.2300', '28.6100'], 'type': 'Point'},
                'properties': {'country': 'India', 'name': 'Delhi'},
                'type': 'Feature'
            },
        ]
        self.assertEqual(features, expected_features)

    def _table_data(self, geo_property_header=None):
        data = [self._table_header(geo_property_header)]
        table_data_rows = self._table_data_rows
        [data.append(row) for row in table_data_rows]
        return data

    def _table_header(self, geo_property_header=None):
        geo_property_header = self.GEO_PROPERTY if geo_property_header is None else geo_property_header
        return [
            'name',
            geo_property_header,
            'country',
        ]

    @property
    def _table_data_rows(self):
        return [
            ['Boston', '42.361145 -71.057083 0 0', 'United States'],
            ['Cape Town', '-33.918861 18.423300 0 0', 'South Africa'],
            ['Delhi', '28.6100 77.2300 0 0', 'India']
        ]

    def geopoint_table_configuration(self, selected_geo_property, path_string, header_name=None):
        path = [PathNode(name=node) for node in path_string.split('.')]
        header_name = header_name if header_name is not None else 'MyGPSProperty'

        return TableConfiguration(
            selected=True,
            selected_geo_property=selected_geo_property,
            columns=[
                SplitGPSExportColumn(
                    label=header_name,
                    item=GeopointItem(
                        path=path,
                    ),
                    selected=True,
                )
            ]
        )
