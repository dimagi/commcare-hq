from __future__ import absolute_import
from __future__ import unicode_literals

from corehq.apps.custom_data_fields.models import CustomDataFieldsDefinition, CustomDataField

from ..util import LocationExporter
from ..views import LocationFieldsView
from .util import LocationHierarchyTestCase


class MockExportWriter(object):
    def __init__(self):
        self.data = {}

    def write(self, document_table):
        for table_index, table in document_table:
            self.data[table_index] = list(table)


class TestLocationsExport(LocationHierarchyTestCase):
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
            ])
        ]),
        ('California', [
            ('Los Angeles', []),
        ])
    ]
    custom_fields = ['is_test', 'favorite_color', 'secret_code', 'foo', 'bar', 'baz']

    @classmethod
    def setUpClass(cls):
        super(TestLocationsExport, cls).setUpClass()

        cls.loc_fields = CustomDataFieldsDefinition.get_or_create(cls.domain, LocationFieldsView.field_type)
        cls.loc_fields.fields = [CustomDataField(slug=slug) for slug in cls.custom_fields]
        cls.loc_fields.save()

        cls.boston = cls.locations['Boston']
        cls.boston.metadata = {
            field: field for field in cls.custom_fields
        }
        cls.boston.save()

        exporter = LocationExporter(cls.domain)
        writer = MockExportWriter()
        exporter.write_data(writer)

        cls.headers = dict(exporter.get_headers())
        cls.city_headers = cls.headers['city'][0]
        cls.boston_data = [row for row in writer.data['city'] if row[0] == cls.boston.location_id][0]

    def test_consisent_header_order(self):
        # This intentionally checks both contents and order
        self.assertEqual(
            self.city_headers,
            [
                'location_id',
                'site_code',
                'name',
                'parent_site_code',
                'external_id',
                'latitude',
                'longitude',
                'Delete(Y/N)',
                # The custom data fields have a set order - make sure to preserve that
                'data: is_test',
                'data: favorite_color',
                'data: secret_code',
                'data: foo',
                'data: bar',
                'data: baz',
                'uncategorized_data',
                'Delete Uncategorized Data(Y/N)',
            ]
        )

    def test_custom_data_headers_line_up(self):
        # Boston was set up with location data values that match the keys
        for header, value in zip(self.city_headers, self.boston_data):
            if header.startswith("data: "):
                self.assertEqual(header, "data: {}".format(value))
