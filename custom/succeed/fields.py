from django.utils.translation import ugettext_noop
from corehq.apps.reports.dont_use.fields import ReportSelectField
from corehq.apps.reports.filters.base import BaseSingleOptionFilter
from corehq.elastic import es_query
from corehq.apps.es import CaseES
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
        res = (CaseES('report_cases')
               .domain(self.domain)
               .exists('care_site_display.#value')
               .source('care_site_display')
               .run())
        care_sites = {c['care_site_display']['#value'] for c in res.hits}
        return [{'val': care_site, 'text': care_site}
                for care_site in care_sites]


class ResponsibleParty(ReportSelectField):
    slug = "responsible_party"
    name = ugettext_noop("Responsible Party")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = ugettext_noop("All Roles")

    @property
    def options(self):
        return [
            dict(val='CM', text=CONFIG['cm_role']),
            dict(val='CHW', text=CONFIG['chw_role']),
        ]


class PatientStatus(ReportSelectField):
    slug = "patient_status"
    name = ugettext_noop("Patient Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = "All Patients"
    options = [dict(val="active", text=ugettext_noop("Active")),
               dict(val="not_active", text=ugettext_noop("Not Active"))]


class PatientFormNameFilter(BaseSingleOptionFilter):
    label = ugettext_noop("Form Group")
    slug = "form_name"
    css_class = "span5"
    default_text = 'All Forms'

    @property
    def options(self):
        return [
            ('pm_forms', 'PM Forms'),
            ('cm_forms', 'CM Forms'),
            ('chw_forms', 'CHW Forms'),
            ('task', 'Tasks and Appointments')
        ]


class PatientNameFilterMixin(object):
    slug = "patient_id"
    label = ugettext_noop("Patient Name")
    default_text = ugettext_noop("All Patients")

    @property
    def options(self):
        q = { "query": {
                "filtered": {
                    "query": {
                        "match_all": {}
                    },
                    "filter": {
                        "and": [
                            {"term": {"domain.exact": self.domain}},
                            {"term": {"type.exact": "participant"}},
                        ]
                    }
                }
            }
        }
        es_filters = q["query"]["filtered"]["filter"]
        def _filter_gen(key, flist):
            return {"terms": {
                key: [item.lower() for item in flist if item]
            }}

        user = self.request.couch_user
        if not user.is_web_user():
            owner_ids = user.get_group_ids()
            user_ids = [user._id]
            owner_filters = _filter_gen('owner_id', owner_ids)
            user_filters = _filter_gen('user_id', user_ids)
            filters = filter(None, [owner_filters, user_filters])
            subterms = []
            subterms.append({'or': filters})
            es_filters["and"].append({'and': subterms} if subterms else {})

        es_results = es_query(q=q, es_index='report_cases', dict_only=False)
        return [(case['_source']['_id'], case['_source']['full_name']['#value']) for case in es_results['hits'].get('hits', [])]

class PatientName(PatientNameFilterMixin, BaseSingleOptionFilter):
    placeholder = ugettext_noop('Click to select a patient')

class TaskStatus(ReportSelectField):
    slug = "task_status"
    name = ugettext_noop("Task Status")
    cssId = "opened_closed"
    cssClasses = "span3"
    default_option = ugettext_noop("All Tasks")

    @property
    def options(self):
        return [
            dict(val='open', text=ugettext_noop("Only Open Tasks")),
            dict(val='closed', text=ugettext_noop("Only Closed Tasks")),
        ]
