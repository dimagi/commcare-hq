from django.utils.translation import ugettext_noop
from corehq.apps.groups.models import Group
from corehq.apps.reports.dont_use.fields import ReportSelectField
from corehq.apps.reports.filters.base import BaseDrilldownOptionFilter
from corehq.apps.users.models import CouchUser, WebUser
from corehq.elastic import es_query
from corehq.pillows.mappings.reportcase_mapping import REPORT_CASE_INDEX
from custom.succeed.reports import SUBMISSION_SELECT_FIELDS
from casexml.apps.case.models import CommCareCase
from custom.succeed.utils import (
    CONFIG
)


class CareSite(ReportSelectField):
    slug = "care_site_display"
    name = ugettext_noop("Care Site")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Sites"

    @property
    def options(self):
        q = { "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "bool": {
                            "must": [
                                {"term": {"domain.exact": self.domain}}
                            ],
                            "must_not": []
                        }
                    }
                }
            }
        }
        es_results = es_query(q=q, es_url=REPORT_CASE_INDEX + '/_search', dict_only=False)
        care_sites = []
        for case in es_results['hits'].get('hits', []):
            prop = CommCareCase.get(case['_id']).get_case_property('care_site_display')
            if prop is not None and prop not in care_sites:
                care_sites.append(prop)
        return [dict(val=care_site, text=ugettext_noop(care_site)) for care_site in care_sites]


class ResponsibleParty(ReportSelectField):
    slug = "responsible_party"
    name = ugettext_noop("Responsible Party")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = ugettext_noop("All Roles")

    @property
    def options(self):
        return [
            dict(val=CONFIG['cm_role'], text=ugettext_noop("Care Manager")),
            dict(val=CONFIG['chw_role'], text=ugettext_noop("Community Health Worker")),
        ]


class PatientStatus(ReportSelectField):
    slug = "patient_status"
    name = ugettext_noop("Patient Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Patients"
    options = [dict(val="active", text=ugettext_noop("Active")),
               dict(val="not_active", text=ugettext_noop("Not Active"))]

class PatientFormNameFilter(BaseDrilldownOptionFilter):
    label = ugettext_noop("Filter Forms")
    slug = "form_name"
    css_class = "span5"

    @property
    def drilldown_map(self):
        return SUBMISSION_SELECT_FIELDS

    @classmethod
    def get_labels(cls):
        return [
            ('Form Group', 'All Form Groups', 'group'),
            ('Form Name', 'All Form names', 'xmlns'),
        ]
