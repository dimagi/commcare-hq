from decimal import Decimal

from corehq.apps.custom_data_fields.models import (
    CustomDataFieldsDefinition,
    Field,
)

from ..util import LocationExporter
from ..views import LocationFieldsView
from .util import LocationHierarchyTestCase, MockExportWriter
from corehq.apps.locations.models import SQLLocation


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
        ]),
        ('四川', [
            ('成都', []),
        ])
    ]
    custom_fields = ['is_test', 'favorite_color', 'secret_code', 'foo', '酒吧', 'baz']

    @classmethod
    def setUpClass(cls):
        super(TestLocationsExport, cls).setUpClass()

        cls.loc_fields = CustomDataFieldsDefinition.get_or_create(cls.domain, LocationFieldsView.field_type)
        cls.loc_fields.set_fields([
            Field(slug=slug) for slug in cls.custom_fields
        ])
        cls.loc_fields.save()

        cls.boston = cls.locations['Boston']
        cls.boston.metadata = {
            field: '{}-试验'.format(field) for field in cls.custom_fields + ['不知道']
        }
        cls.boston.external_id = 'external_id'
        cls.boston.latitude = Decimal('42.36')
        cls.boston.longitude = Decimal('71.06')
        cls.boston.save()

        exporter = LocationExporter(cls.domain)
        writer = MockExportWriter()
        exporter.write_data(writer)

        cls.headers = dict(exporter.get_headers())
        cls.city_headers = cls.headers['city'][0]
        cls.boston_data = [row for row in writer.data['city'] if row[0] == cls.boston.location_id][0]


    def test_columns_and_headers_align(self):
        boston = dict(zip(self.city_headers, self.boston_data))
        self.assertEqual(boston['location_id'], self.boston.location_id)
        self.assertEqual(boston['name'], self.boston.name)
        self.assertEqual(boston['site_code'], self.boston.site_code)
        self.assertEqual(boston['external_id'], self.boston.external_id)
        self.assertEqual(boston['latitude'], self.boston.latitude)
        self.assertEqual(boston['longitude'], self.boston.longitude)
        for field in self.custom_fields:
            self.assertEqual(boston['data: {}'.format(field)], self.boston.metadata[field])

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
                'data: 酒吧',
                'data: baz',
                'uncategorized_data',
                'Delete Uncategorized Data(Y/N)',
            ]
        )

    def test_custom_data_headers_line_up(self):
        # Boston was set up with location data values that match the keys
        for header, value in zip(self.city_headers, self.boston_data):
            if header.startswith("data: "):
                self.assertEqual("{}-试验".format(header), "data: {}".format(value))

    def test_no_root_location_id(self):
        domain_locations_count = SQLLocation.objects.filter(domain=self.domain).count()
        exporter = LocationExporter(self.domain)

        self.assertEqual(domain_locations_count, exporter.base_query.count())

    def test_root_location_id_supplied(self):
        location = SQLLocation.objects.get(domain=self.domain, name='Suffolk')
        exporter = LocationExporter(
            self.domain,
            root_location_id=location.location_id,
        )

        self.assertEqual(exporter.base_query.count(), 2)

    def test_selected_location_only(self):
        location = SQLLocation.objects.get(domain=self.domain, name='Suffolk')
        exporter = LocationExporter(
            self.domain,
            root_location_id=location.location_id,
            selected_location_only=True,
        )

        self.assertEqual(exporter.base_query.count(), 1)

    def test_no_root_location_id_supplied_archived_only(self):
        archived_locations_count = SQLLocation.objects.filter(domain=self.domain, is_archived=True).count()
        exporter = LocationExporter(
            self.domain,
            is_archived=True,
        )
        self.assertEqual(exporter.base_query.count(), archived_locations_count)

    def test_root_location_id_supplied_archived_only(self):
        # see also test_root_location_id_supplied
        location = SQLLocation.objects.get(domain=self.domain, name='Suffolk')
        location.is_archived = True
        location.save()

        exporter = LocationExporter(
            self.domain,
            is_archived=True,
            root_location_id=location.location_id,
        )

        self.assertEqual(exporter.base_query.count(), 1)
        self.assertEqual(exporter.base_query[0].name, 'Suffolk')

        # Reset to previous state
        location.is_archived = False
        location.save()

    def test_root_location_id_supplied_active_only(self):
        # see also test_root_location_id_supplied
        location = SQLLocation.objects.get(domain=self.domain, name='Suffolk')
        location.is_archived = True
        location.save()

        exporter = LocationExporter(
            self.domain,
            is_archived=False,
            root_location_id=location.location_id,
        )

        self.assertEqual(exporter.base_query.count(), 1)
        self.assertEqual(exporter.base_query[0].name, 'Boston')

        # Reset to previous state
        location.is_archived = False
        location.save()
