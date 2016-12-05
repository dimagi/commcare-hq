import uuid
from django.test import TestCase
from pillowtop.feed.interface import Change

from corehq.apps.domain.shortcuts import create_domain
from corehq.apps.locations.document_store import get_location_change_meta
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.locations.tests.util import delete_all_locations

from corehq.apps.userreports.app_manager import _clean_table_name
from corehq.apps.userreports.models import DataSourceConfiguration
from corehq.apps.userreports.pillow import get_kafka_ucr_pillow
from corehq.apps.userreports.tasks import rebuild_indicators
from corehq.apps.userreports.util import get_indicator_adapter


class TestLocationDataSource(TestCase):
    domain = "delos_corp"

    def setUp(self):
        delete_all_locations()
        self.domain_obj = create_domain(self.domain)

        self.region = LocationType.objects.create(domain=self.domain, name="region")
        self.town = LocationType.objects.create(domain=self.domain, name="town", parent_type=self.region)

        self.data_source_config = DataSourceConfiguration(
            domain=self.domain,
            display_name='Locations in Westworld',
            referenced_doc_type='Location',
            table_id=_clean_table_name(self.domain, str(uuid.uuid4().hex)),
            configured_filter={},
            configured_indicators=[{
                "type": "expression",
                "expression": {
                    "type": "property_name",
                    "property_name": "name"
                },
                "column_id": "location_name",
                "display_name": "location_name",
                "datatype": "string"
            }],
        )
        self.data_source_config.validate()
        self.data_source_config.save()

        self.pillow = get_kafka_ucr_pillow()
        self.pillow.bootstrap(configs=[self.data_source_config])

    def tearDown(self):
        self.domain_obj.delete()
        delete_all_locations()
        self.data_source_config.delete()

    def _make_loc(self, name, location_type):
        return SQLLocation.objects.create(
            domain=self.domain, name=name, site_code=name, location_type=location_type)

    @staticmethod
    def location_to_change(location, is_deletion=False):
        change_meta = get_location_change_meta(location.domain, location.location_id, is_deletion)
        return Change(
            id=location.location_id,
            sequence_id='0',
            deleted=is_deletion,
            document=location.to_json(),
            metadata=change_meta,
        )

    def assertDataSourceAccurate(self, expected_locations):
        adapter = get_indicator_adapter(self.data_source_config)
        query = adapter.get_query_object()
        adapter.refresh_table()
        data_source = query.all()
        self.assertItemsEqual(
            expected_locations,
            [row[-1] for row in data_source]
        )

    def test_location_data_source(self):
        self._make_loc("Westworld", self.region)
        sweetwater = self._make_loc("Sweetwater", self.town)
        las_mudas = self._make_loc("Las Mudas", self.town)

        rebuild_indicators(self.data_source_config._id)

        self.assertDataSourceAccurate(["Westworld", "Sweetwater", "Las Mudas"])

        # Insert new location
        blood_arroyo = self._make_loc("Blood Arroyo", self.town)
        self.pillow.process_change(self.location_to_change(blood_arroyo))
        self.assertDataSourceAccurate(["Westworld", "Sweetwater", "Las Mudas", "Blood Arroyo"])

        # Change an existing location
        sweetwater.name = "Pariah"
        sweetwater.save()
        self.pillow.process_change(self.location_to_change(sweetwater))
        self.assertDataSourceAccurate(["Westworld", "Pariah", "Las Mudas", "Blood Arroyo"])

        # Delete a location
        change = self.location_to_change(las_mudas, is_deletion=True)
        las_mudas.delete()
        self.pillow.process_change(change)
        # No actual change - deletions are not yet processed
        self.assertDataSourceAccurate(["Westworld", "Pariah", "Las Mudas", "Blood Arroyo"])
