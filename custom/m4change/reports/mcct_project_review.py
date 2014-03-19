from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from jsonobject import DateTimeProperty
from corehq import Domain
from corehq.apps.commtrack.util import get_commtrack_location_id
from corehq.apps.locations.models import Location
from corehq.elastic import ES_URLS

from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import StrongFilterUsersField
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from corehq.elastic import es_query
from custom.m4change.constants import BOOKING_FORMS, FOLLOW_UP_FORMS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, IMMUNIZATION_FORMS
from custom.m4change.models import McctStatus
from custom.m4change.utils import get_case_by_id, get_user_by_id, get_property, get_form_ids_by_status
from custom.m4change.constants import EMPTY_FIELD


class McctProjectReview(CustomProjectReport, ElasticProjectInspectionReport, ProjectReport,
                        ProjectReportParametersMixin, MultiFormDrilldownMixin, DatespanMixin):
    name = 'mCCT Project Review Page'
    slug = 'mcct_project_review_page'
    emailable = False
    exportable = True
    asynchronous = True
    ajax_pagination = True
    include_inactive = True

    fields = [
        'custom.m4change.fields.DateRangeField',
        'custom.m4change.fields.CaseSearchField'
    ]

    base_template = 'reports/report.html'
    report_template_path = 'reports/selectTemplate.html'
    filter_users_field_class = StrongFilterUsersField


    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Date of service"), prop_name="form.meta.timeEnd"),
            DataTablesColumn(_("Client Name"), sortable=False),
            DataTablesColumn(_("Service Type"), sortable=False),
            DataTablesColumn(_("Health Facility"), sortable=False),
            DataTablesColumn(_("Card No."), sortable=False),
            DataTablesColumn(_("LGA"), sortable=False),
            DataTablesColumn(_("Phone No."), sortable=False),
            DataTablesColumn(_("Amount due"), sortable=False),
            DataTablesColumn(mark_safe('Status/Action  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> '
                                       '<a href="#" class="select-none btn btn-mini btn-warning">none</a>'),
                                        sortable=False, span=3))
        return headers

    @property
    def es_results(self):
        if not getattr(self, 'es_response', None):
            self.es_query()
        return self.es_response

    def _get_filtered_cases(self):
        case_search = self.request.GET.get("case_search", "")
        if len(case_search) == 0:
            return []

        query = {
            "query": {
                "query_string": {
                    "default_field": "_all",
                    "query": case_search
                }
            }
        }
        es_response = es_query(params={"domain.exact": self.domain}, q=query, es_url=ES_URLS.get('cases'))
        return [res['_source']['_id'] for res in es_response.get('hits', {}).get('hits', [])]

    def es_query(self):
        if not getattr(self, 'es_response', None):
            range = self.request_params.get('range', None)
            start_date = None
            end_date = None
            if range is not None:
                dates = str(range).split(_(" to "))
                start_date = dates[0]
                end_date = dates[1]
            filtered_case_ids = self._get_filtered_cases()
            exclude_form_ids = [mcct_status.form_id for mcct_status in McctStatus.objects.filter(domain=self.domain)]
            q = {
                "query": {
                    "range": {
                        "form.meta.timeEnd": {
                            "from": start_date,
                            "to": end_date,
                            "include_upper": False
                        }
                    }
                },
                "filter": {
                    "and": [
                        {"term": {"doc_type": "xforminstance"}},
                        {"not": {"missing": {"field": "xmlns"}}},
                        {"not": {"missing": {"field": "form.meta.userID"}}}
                    ]
                }
            }

            if len(exclude_form_ids) > 0:
                q["filter"]["and"].append({"not": {"ids": {"values": exclude_form_ids}}})
            if len(filtered_case_ids) > 0:
                case_ids_str = " OR ".join(filtered_case_ids)
                q["filter"]["and"].append({
                    "query": {
                        "query_string": {
                            "default_field": "form.case.@case_id",
                            "query": case_ids_str
                        }
                    }
                })

            allforms = BOOKING_FORMS + FOLLOW_UP_FORMS + BOOKED_AND_UNBOOKED_DELIVERY_FORMS + IMMUNIZATION_FORMS
            xmlnss = filter(None, [form for form in allforms])
            if xmlnss:
                q["filter"]["and"].append({"terms": {"xmlns.exact": xmlnss}})

            modify_close = filter(None, [u'Modify/Close Client'])
            q["filter"]["and"].append({"not": {"terms": {"form.@name": modify_close}}})

            q["sort"] = self.get_sorting_block() \
                if self.get_sorting_block() else [{"form.meta.timeEnd" : {"order": "desc"}}]
            self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'),
                                        start_at=self.pagination.start, size=self.pagination.count)
        return self.es_response

    @property
    def total_records(self):
        return int(self.es_results['hits']['total'])

    @property
    def rows(self):
        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        for form in submissions:
            try:
                case_id = form["form"]["case"]["@case_id"]
                case = get_case_by_id(case_id)
            except KeyError:
                case = EMPTY_FIELD
                case_id = EMPTY_FIELD

            amount_due = EMPTY_FIELD
            service_type = EMPTY_FIELD
            visits = form["form"].get("visits")
            form_id = form["_id"]
            location_name = EMPTY_FIELD
            location_parent_name = EMPTY_FIELD

            if case is not EMPTY_FIELD:
                user_id = get_property(case, "user_id", EMPTY_FIELD)
                user = get_user_by_id(user_id)
                location_id = get_commtrack_location_id(user, Domain.get_by_name(self.domain))
                if location_id is not None:
                    location = Location.get(location_id)
                    location_name = location.name
                    location_parent = location.parent
                    location_parent_name = location_parent.name if location_parent is not None else EMPTY_FIELD

            if form["xmlns"] in IMMUNIZATION_FORMS:
                service_type = _("Immunization")
                amount_due = 1000
            elif form["xmlns"] in BOOKED_AND_UNBOOKED_DELIVERY_FORMS:
                service_type = _("Delivery")
                amount_due = 2000
            elif visits == "1":
                service_type = _("First Antenatal")
                amount_due = 1000
            elif visits == "2":
                service_type = _("Second Antenatal")
                amount_due = 300
            elif visits == "3":
                service_type = _("Third Antenatal")
                amount_due = 300
            elif visits == "4":
                service_type = _("Fourth Antenatal")
                amount_due = 400

            checkbox = mark_safe('<input type="checkbox" class="selected-element" '
                                 'data-bind="event: {change: updateSelection}" data-formid="%(form_id)s" '
                                 'data-caseid="%(case_id)s" data-servicetype="%(service_type)s"/>')

            yield [
                DateTimeProperty().wrap(form["form"]["meta"]["timeEnd"]).strftime("%Y-%m-%d"),
                get_property(case, "full_name", EMPTY_FIELD),
                service_type,
                location_name,
                get_property(case, "card_number", EMPTY_FIELD),
                location_parent_name,
                get_property(case, "phone_number", EMPTY_FIELD),
                amount_due,
                checkbox % dict(form_id=form_id, case_id=case_id, service_type=service_type)
            ]

class McctClientApprovalPage(McctProjectReview):
    name = 'mCCT client Approval Page'
    slug = 'mcct_client_approval_page'
    report_template_path = 'reports/approveStatus.html'
    display_status = 'reviewed'

    def es_query(self):
        reviewed_form_ids = get_form_ids_by_status(self.domain, getattr(self, 'display_status', None))
        if len(reviewed_form_ids) > 0:
            if not getattr(self, 'es_response', None):
                form_ids_str = " OR ".join(reviewed_form_ids)
                range = self.request_params.get('range', None)
                start_date = None
                end_date = None
                if range is not None:
                    dates = str(range).split(_(" to "))
                    start_date = dates[0]
                    end_date = dates[1]
                filtered_case_ids = self._get_filtered_cases()
                q = {
                    "query": {
                        "range": {
                            "form.meta.timeEnd": {
                                "from": start_date,
                                "to": end_date,
                                "include_upper": False
                            }
                        }
                    },
                    "filter": {
                        "and": [{'query': {
                            'query_string': {
                                "default_field": "form.meta.instanceID",
                                "query": form_ids_str
                                }
                        }}
                        ]
                    }
                }

                if len(filtered_case_ids) > 0:
                    case_ids_str = " OR ".join(filtered_case_ids)
                    q["filter"]["and"].append({
                        "query": {
                            "query_string": {
                                "default_field": "form.case.@case_id",
                                "query": case_ids_str
                            }
                        }
                    })

                q["sort"] = self.get_sorting_block() if self.get_sorting_block() else [{"form.meta.timeEnd" : {"order": "desc"}}]
                self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'),
                                            start_at=self.pagination.start, size=self.pagination.count)
        else:
            self.es_response = {'hits': {'total': 0}}

        return self.es_response


class McctClientPaymentPage(McctClientApprovalPage):
    name = 'mCCT client Payment Page'
    slug = 'mcct_client_payment_page'
    report_template_path = 'reports/paidStatus.html'
    display_status = 'approved'


class McctRejectedClientPage(McctClientApprovalPage):
    name = 'mCCT Rejected clients Page'
    slug = 'mcct_rejected_clients_page'
    report_template_path = 'reports/activateStatus.html'
    display_status = 'rejected'
