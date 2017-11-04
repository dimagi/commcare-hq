from __future__ import absolute_import
from corehq.apps.fixtures.models import FixtureDataItem, FixtureDataType
from corehq.apps.reports.dont_use.fields import ReportSelectField
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from corehq.apps.reports.filters.dates import DatespanFilter
from corehq.apps.reports.filters.fixtures import MultiLocationFilter

from custom.apps.gsid.reports.sql_reports import (
    GSIDSQLByAgeReport,
    GSIDSQLByDayReport,
    GSIDSQLPatientReport,
    GSIDSQLTestLotsReport,
    PatientMapReport,
)
from .util import get_unique_combinations


class AsyncClinicField(MultiLocationFilter):
    label = "Location"
    slug = "clinic"
    hierarchy = [{"type": "country", "display": "country_name"},
                 {"type": "province", "parent_ref": "country_id", "references": "country_id", "display": "province_name"},
                 {"type": "district", "parent_ref": "province_id", "references": "province_id", "display": "district_name"},
                 {"type": "clinic", "parent_ref": "district_id", "references": "district_id", "display": "clinic_name"}]


class TestField(BaseDrilldownOptionFilter):
    label = "Disease/Test Type"
    slug = "test_type"

    @property
    def drilldown_map(self):
        diseases = []
        disease_fixtures = FixtureDataItem.by_data_type(
            self.domain, 
            FixtureDataType.by_domain_tag(self.domain, "diseases").one()
        )
        for d in disease_fixtures:
            disease = dict(
                val="%(name)s:%(uid)s" % {'name': d.fields_without_attributes["disease_id"], 'uid': d.get_id}, 
                text=d.fields_without_attributes["disease_name"]
            )
            tests = []
            test_fixtures = FixtureDataItem.by_field_value(
                self.domain, 
                FixtureDataType.by_domain_tag(self.domain, "test").one(),
                "disease_id",
                d.fields_without_attributes["disease_id"]
            )
            for t in test_fixtures:
                tests.append(dict(
                    val="%(name)s:%(uid)s" % {'name': t.fields_without_attributes["test_name"], 'uid': t.get_id}, 
                    text=t.fields_without_attributes["visible_test_name"])
                )
            disease['next'] = tests
            diseases.append(disease)

        return diseases

    @classmethod
    def get_labels(cls):
        return [
            ('Disease', 'All diseases', 'disease'),
            ('Test Type', 'All test types', 'test'),
        ]


class AggregateAtField(ReportSelectField):
    slug = "aggregate_at"
    name = "Group By"
    cssId = "aggregate_at_select"
    cssClasses = "span2"
    field_opts = ["Country", "Province", "District", "Clinic"]

    @property
    def default_option(self):
        return "Default: %s" % self.field_opts[-1]

    def update_params(self):
        self.selected = self.request.GET.get(self.slug, '')
        self.options = [{'val': f.lower(), 'text': f} for f in [fo for fo in self.field_opts if fo != self.selected]]


class RelativeDatespanField(DatespanFilter):
    template = "relative_date.html"

CUSTOM_REPORTS = (
    ('Custom Reports', (
        GSIDSQLPatientReport,
        GSIDSQLByDayReport,
        GSIDSQLTestLotsReport,
        GSIDSQLByAgeReport,
        PatientMapReport
    )),
)
