from __future__ import absolute_import
from django.test import override_settings, TestCase
from mock import MagicMock, patch

from sqlagg.filters import EQ, OR

from corehq.apps.userreports.models import ReportConfiguration, DataSourceConfiguration
from corehq.apps.userreports.reports.factory import ReportFactory
from corehq.apps.userreports.reports.view import get_filter_values
from custom.enikshay.tests.utils import ENikshayLocationStructureMixin
from six.moves import range


@override_settings(TESTS_SHOULD_USE_SQL_BACKEND=True)
class LocationHierarchyFilterTests(ENikshayLocationStructureMixin, TestCase):

    domain = "location-filter-test-domain"

    def assertFiltersEqual(self, filter_1, filter_2):
        self.assertEqual(type(filter_1), type(filter_2))
        if isinstance(filter_1, OR):
            self.assertEqual(len(filter_1.filters), len(filter_2.filters))
            for i in range(len(filter_1.filters)):
                self.assertFiltersEqual(filter_1.filters[i], filter_2.filters[i])
        elif isinstance(filter_1, EQ):
            self.assertEqual(filter_1.column_name, filter_2.column_name)
            self.assertEqual(filter_1.parameter, filter_2.parameter)

        else:
            # Need to implement other filter types
            raise NotImplementedError(
                "assertFiltersEqual has not been defined for {} type filters".format(type(filter_1))
            )

    def test_filter(self):
        slug = "hierarchy_filter_slug"
        filter_spec = {
            "type": "enikshay_location_hierarchy",
            "display": "location hierarchy",
            "datatype": "string",
            "slug": slug,
            "field": "does_not_matter",
        }
        data_source_config = DataSourceConfiguration(
            domain=self.domain,
            referenced_doc_type="",
            table_id="123",
        )

        with patch(
                "corehq.apps.userreports.reports.data_source.get_datasource_config",
                MagicMock(return_value=(data_source_config, None))
        ):
            report_config = ReportConfiguration(
                config_id="123",
                filters=[filter_spec]
            )
            report = ReportFactory().from_spec(report_config)
            filter_values = get_filter_values(
                report_config.ui_filters,
                {slug: self.cto.location_id},
                user=MagicMock(),
            )
            report.set_filter_values(filter_values)

        expected_filter_vals = {
            '{}_sto'.format(slug): self.sto.location_id,
            '{}_cto'.format(slug): self.cto.location_id,
            '{}_below_cto'.format(slug): self.cto.location_id,
        }
        expected_filter = OR([
            EQ("sto", "{}_sto".format(slug)),
            EQ("cto", "{}_cto".format(slug)),
            EQ("below_cto", "{}_below_cto".format(slug))
        ])

        self.assertEqual(len(report.data_source.filters), 1)
        self.assertFiltersEqual(
            report.data_source.filters[0],
            expected_filter
        )
        self.assertEqual(
            report.data_source.filter_values,
            expected_filter_vals
        )
