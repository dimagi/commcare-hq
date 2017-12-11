from __future__ import absolute_import
from django.http import HttpRequest
from django.test import override_settings

from corehq.apps.locations.tests.util import LocationHierarchyTestCase

from ..const import UCR_SQL_BACKEND
from ..models import DataSourceConfiguration, ReportConfiguration
from ..reports.view import ConfigurableReport
from ..tasks import rebuild_indicators
from ..tests.test_view import ConfigurableReportTestMixin
from ..util import get_indicator_adapter


@override_settings(OVERRIDE_UCR_BACKEND=UCR_SQL_BACKEND)
class TestReportLocationAggregationSQL(ConfigurableReportTestMixin, LocationHierarchyTestCase):
    """
    """
    location_type_names = ['state', 'county', 'city']
    location_structure = [
        ('Massachusetts', [
            ('Middlesex', [
                ('Cambridge', []),
                ('Somerville', []),
            ]),
            ('Suffolk', [
                ('Boston', []),
                ('Brookline', []),
            ])
        ])
    ]

    @classmethod
    def _create_data(cls):
        """
        Populate the database with some cases
        """
        for name, forms_submitted, state, county, city in [
            ("Rick Deckard", 1, "Massachusetts", "Middlesex", "Cambridge"),
            ("Gaff", 10, "Massachusetts", "Middlesex", "Somerville"),
            ("Rachael Tyrell", 100, "Massachusetts", "Suffolk", "Boston"),
        ]:
            cls._new_case({
                "name": name,
                "forms_submitted": forms_submitted,
                "num_patients": 1,
                "state_id": cls.locations[state].location_id,
                "county_id": cls.locations[county].location_id,
                "city_id": cls.locations[city].location_id,
                "location_id": cls.locations[city].location_id,
            }).save()

    @classmethod
    def _create_data_source(cls):
        cls.data_source = DataSourceConfiguration(
            domain=cls.domain,
            display_name=cls.domain,
            referenced_doc_type='CommCareCase',
            table_id="foo",
            configured_filter={
                "type": "boolean_expression",
                "operator": "eq",
                "expression": {
                    "type": "property_name",
                    "property_name": "type"
                },
                "property_value": cls.case_type,
            },
            configured_indicators=[
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": property_name,
                    },
                    "column_id": property_name,
                    "display_name": property_name,
                    "datatype": "string",
                }
                for property_name in [
                    "name", "state_id", "county_id", "city_id", "location_id",
                ]
            ] + [
                {
                    "type": "expression",
                    "expression": {
                        "type": "property_name",
                        "property_name": property_name,
                    },
                    "column_id": property_name,
                    "display_name": property_name,
                    "datatype": "integer",
                }
                for property_name in ["forms_submitted", "num_patients"]
            ],
        )
        cls.data_source.validate()
        cls.data_source.save()
        rebuild_indicators(cls.data_source._id)
        cls.adapter = get_indicator_adapter(cls.data_source)
        cls.adapter.refresh_table()

    @classmethod
    def setUpClass(cls):
        super(TestReportLocationAggregationSQL, cls).setUpClass()
        cls._create_data()
        cls._create_data_source()

    @classmethod
    def tearDownClass(cls):
        cls.adapter.drop_table()
        cls._delete_everything()
        super(TestReportLocationAggregationSQL, cls).tearDownClass()

    def _create_report(self, aggregation_columns, columns, sort_expression=None):
        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=self.data_source._id,
            title='foo',
            aggregation_columns=aggregation_columns,
            columns=columns,
        )
        if sort_expression:
            report_config.sort_expression = sort_expression
        report_config.save()
        return report_config

    def test_foo(self):
        report_config = ReportConfiguration(
            domain=self.domain,
            config_id=self.data_source._id,
            title='foo',
            aggregation_columns=["county_id"],
            columns=[
                {
                    "type": "field",
                    "display": "county_id",
                    "field": "county_id",
                    "column_id": "county_id",
                    "aggregation": "simple",
                },
                {
                    "type": "field",
                    "display": "forms_submitted",
                    "field": "forms_submitted",
                    "column_id": "forms_submitted",
                    "aggregation": "sum",
                },
                {
                    "type": "field",
                    "display": "num_patients",
                    "field": "num_patients",
                    "column_id": "num_patients",
                    "aggregation": "sum",
                },
            ],
            filters=[],
        )
        report_config.save()

        view = ConfigurableReport(request=HttpRequest())
        view._domain = self.domain
        view._lang = "en"
        view._report_config_id = report_config._id

        from pprint import pprint
        pprint(view.export_table)
