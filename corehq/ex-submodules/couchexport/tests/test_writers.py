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
from corehq.apps.export.models import (
    TableConfiguration,
    SplitGPSExportColumn,
    GeopointItem,
    PathNode,
    ExportColumn,
    ExportItem,
)
from corehq.apps.export.models.new import (
    GPS_SPLIT_COLUMN_LONGITUDE_TEMPLATE,
    GPS_SPLIT_COLUMN_LATITUDE_TEMPLATE,
)


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

    def _table_data(self, table, multi_column=False):
        data = [table.get_headers(split_columns=multi_column)]
        table_data_rows = self._table_data_rows(multi_column=multi_column)
        [data.append(row) for row in table_data_rows]
        return data

    def _table_data_rows(self, multi_column):
        def row_data(city, home, country, location_meta):
            home_data = home.split(" ") if multi_column else [home]
            location_meta_data = location_meta.split(" ") if multi_column else [location_meta]
            return [city, *home_data, country, *location_meta_data]

        return [
            row_data("Boston", "42.361145 -71.057083 0 0", "United States", "42.361146 -71.057084 100 0"),
            row_data("Cape Town", "-33.918861 18.423300 0 0", "South Africa", "-33.918862 18.423301 100 0"),
            row_data("Delhi", "28.6100 77.2300 0 0", "India", "28.6101 77.2301 100 0")
        ]

    def geopoint_table_configuration(self, selected_geo_property):
        location_metadata_column = self.create_export_column(
            label='location',
            path_string='form.meta.location',
            column_class=SplitGPSExportColumn,
            column_item=GeopointItem,
        )
        other_location_column = self.create_export_column(
            label='form.home',
            path_string="form.home",
            column_class=SplitGPSExportColumn,
            column_item=GeopointItem,
        )
        city_column = self.create_export_column(
            label='form.city',
            path_string='form.name',
            column_class=ExportColumn,
            column_item=ExportItem,
        )
        country_column = self.create_export_column(
            label='form.country',
            path_string='form.country',
            column_class=ExportColumn,
            column_item=ExportItem,
        )

        return TableConfiguration(
            selected=True,
            selected_geo_property=selected_geo_property,
            columns=[
                city_column,
                other_location_column,
                country_column,
                location_metadata_column,
            ]
        )

    @staticmethod
    def create_export_column(label, path_string, column_class, column_item):
        path = [PathNode(name=node) for node in path_string.split('.')]
        return column_class(
            label=label,
            item=column_item(
                path=path,
            ),
            selected=True,
        )

    def test_get_features(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="form.home",
        )
        features = GeoJSONWriter().get_features(table, self._table_data(table=table))

        expected_features = [
            {
                'geometry': {'coordinates': ['-71.057083', '42.361145'], 'type': 'Point'},
                'properties': {
                    'form.country': 'United States',
                    'form.city': 'Boston',
                    'location': '42.361146 -71.057084 100 0',
                },
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['18.423300', '-33.918861'], 'type': 'Point'},
                'properties': {
                    'form.country': 'South Africa',
                    'form.city': 'Cape Town',
                    'location': '-33.918862 18.423301 100 0',
                },
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['77.2300', '28.6100'], 'type': 'Point'},
                'properties': {
                    'form.country': 'India',
                    'form.city': 'Delhi',
                    'location': '28.6101 77.2301 100 0',
                },
                'type': 'Feature'
            },
        ]
        self.assertEqual(features, expected_features)

    def test_get_features__other_geo_property_configured(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="form.not_home",
        )
        features = GeoJSONWriter().get_features(table, self._table_data(table=table))
        self.assertEqual(features, [])

    def test_get_features__invalid_geo_property_column_value(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="form.home",
        )
        data = self._table_data(table=table)

        data[1][1] = "not-a-geo-coordinate-value"
        corrupt_country = data[1][2]

        features = GeoJSONWriter().get_features(table, data)
        features_names = [feature['properties']['form.country'] for feature in features]

        self.assertTrue(corrupt_country not in features_names)

    def test_get_features_from_path__location_metadata(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="form.meta.location",
        )
        features = GeoJSONWriter().get_features(table, self._table_data(table=table))
        expected_features = [
            {
                'geometry': {'coordinates': ['-71.057084', '42.361146'], 'type': 'Point'},
                'properties': {
                    'form.country': 'United States',
                    'form.city': 'Boston',
                    'form.home': '42.361145 -71.057083 0 0'
                },
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['18.423301', '-33.918862'], 'type': 'Point'},
                'properties': {
                    'form.country': 'South Africa',
                    'form.city': 'Cape Town',
                    'form.home': '-33.918861 18.423300 0 0',
                },
                'type': 'Feature'
            },
            {
                'geometry': {'coordinates': ['77.2301', '28.6101'], 'type': 'Point'},
                'properties': {
                    'form.country': 'India',
                    'form.city': 'Delhi',
                    'form.home': '28.6100 77.2300 0 0',
                },
                'type': 'Feature'
            },
        ]
        self.assertEqual(features, expected_features)

    def test_get_features_multiple_columns(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="form.home",
        )
        table.split_multiselects = True
        features = GeoJSONWriter().get_features(table, self._table_data(table=table, multi_column=True))

        feature_coordinates = [feature['geometry']['coordinates'] for feature in features]
        expected_coordinates = [
            ["-71.057083", "42.361145"],
            ["18.423300", "-33.918861"],
            ["77.2300", "28.6100"],
        ]
        self.assertEqual(feature_coordinates, expected_coordinates)

    def test_get_features_from_path_multiple_columns(self):
        table = self.geopoint_table_configuration(
            selected_geo_property="form.meta.location",
        )
        table.split_multiselects = True
        features = GeoJSONWriter().get_features(table, self._table_data(table=table, multi_column=True))

        feature_coordinates = [feature['geometry']['coordinates'] for feature in features]
        expected_coordinates = [
            ["-71.057084", "42.361146"],
            ["18.423301", "-33.918862"],
            ["77.2301", "28.6101"],
        ]
        self.assertEqual(feature_coordinates, expected_coordinates)

    def test_find_geo_data_column(self):
        header = GeoJSONWriter.find_geo_data_column(
            headers=["name", "home"],
            geo_property_name="home"
        )
        self.assertEqual(header, 1)

    def test_find_geo_data_column_invalid(self):
        header = GeoJSONWriter.find_geo_data_column(
            headers=["name", "home"],
            geo_property_name="town"
        )
        self.assertEqual(header, None)

    def test_find_geo_data_columns(self):
        geo_prop = "home"
        header = GeoJSONWriter.find_geo_data_columns(
            headers=[
                "name",
                GPS_SPLIT_COLUMN_LATITUDE_TEMPLATE.format(geo_prop),
                GPS_SPLIT_COLUMN_LONGITUDE_TEMPLATE.format(geo_prop),
            ],
            geo_property_name=geo_prop,
        )
        self.assertEqual(header, [1, 2])

    def test_find_geo_data_columns_swapped(self):
        geo_prop = "home"
        header = GeoJSONWriter.find_geo_data_columns(
            headers=[
                "name",
                GPS_SPLIT_COLUMN_LONGITUDE_TEMPLATE.format(geo_prop),
                GPS_SPLIT_COLUMN_LATITUDE_TEMPLATE.format(geo_prop),
            ],
            geo_property_name=geo_prop,
        )
        self.assertEqual(header, [2, 1])

    def test_find_geo_data_columns_invalid(self):
        geo_prop = "town"
        header = GeoJSONWriter.find_geo_data_columns(
            headers=["name", "home"],
            geo_property_name=geo_prop,
        )
        self.assertEqual(header, [])

    def test_collect_geo_data(self):
        table_headers = ["city", "home"]
        row = ["Texas", "lat lng"]
        coordinates, properties = GeoJSONWriter.collect_geo_data(table_headers, row, 1)

        self.assertEqual(coordinates['lat'], 'lat')
        self.assertEqual(coordinates['lng'], 'lng')
        self.assertEqual(properties, {'city': 'Texas'})

    def test_collect_geo_data_invalid_coordinate(self):
        table_headers = ["city", "home"]
        row = ["Texas", "latlng"]
        coordinates, properties = GeoJSONWriter.collect_geo_data(table_headers, row, 1)

        self.assertEqual(coordinates, {})
        self.assertEqual(properties, {})

    def test_collect_geo_data_multi_column(self):
        geo_prop = "home"
        table_headers = [
            "city",
            GPS_SPLIT_COLUMN_LATITUDE_TEMPLATE.format(geo_prop),
            GPS_SPLIT_COLUMN_LONGITUDE_TEMPLATE.format(geo_prop),
        ]
        row = ["Texas", "lat", "lng"]
        coordinates, properties = GeoJSONWriter.collect_geo_data_multi_column(table_headers, row, [1, 2])

        self.assertEqual(coordinates['lat'], 'lat')
        self.assertEqual(coordinates['lng'], 'lng')
        self.assertEqual(properties, {'city': 'Texas'})
