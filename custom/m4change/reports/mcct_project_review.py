from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _

from jsonobject import DateTimeProperty

from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.fields import StrongFilterUsersField
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from corehq.elastic import es_query
from corehq.pillows.mappings.case_mapping import CASE_INDEX
from corehq.pillows.mappings.xform_mapping import XFORM_INDEX
from casexml.apps.case.models import CommCareCase
from custom.m4change.constants import BOOKING_FORMS, FOLLOW_UP_FORMS, BOOKED_AND_UNBOOKED_DELIVERY_FORMS, IMMUNIZATION_FORMS
from custom.m4change.models import McctStatus

EMPTY_FIELD = "---"


def get_property(dict_obj, name, default=None):
    if name in dict_obj:
        if type(dict_obj[name]) is dict:
            return dict_obj[name]["#value"]
        return dict_obj[name]
    else:
        return default if default is not None else EMPTY_FIELD


class McctProjectReview(CustomProjectReport, ElasticProjectInspectionReport, ProjectReport, ProjectReportParametersMixin, MultiFormDrilldownMixin, DatespanMixin):
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
            #DataTablesColumn(_("Health Facility"), sortable=False),
            DataTablesColumn(_("Card No."), sortable=False),
            #DataTablesColumn(_("LGA"), sortable=False),
            DataTablesColumn(_("Phone No."), sortable=False),
            DataTablesColumn(_("Amount due"), sortable=False),
            DataTablesColumn(mark_safe('Status/Action  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> <a href="#" class="select-none btn btn-mini btn-warning">none</a>'), sortable=False, span=3))
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
        es_response = es_query(params={"domain.exact": self.domain}, q=query, es_url=CASE_INDEX + '/case/_search')
        return [res['_source']['_id'] for res in es_response.get('hits', {}).get('hits', [])]

    def es_query(self):
        # try:
        #     for ob in McctStatus.objects.filter(domain=self.domain):
        #         ob.form_id
        # except McctStatus.DoesNotExist:
        #     status_list = None

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
            # try:
            #     for ob in McctStatus.objects.filter(domain=self.domain):
            #         q["filter"][ob.form_id
            # except McctStatus.DoesNotExist:
            #     status_list = None
            q["sort"] = self.get_sorting_block() if self.get_sorting_block() else [{"form.meta.timeEnd" : {"order": "desc"}}]
            self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=XFORM_INDEX + '/xform/_search',
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
                case = CommCareCase.get(form["form"]["case"]["@case_id"])
                case_id = form["form"]["case"]["@case_id"]
            except KeyError:
                case = EMPTY_FIELD
                case_id = EMPTY_FIELD

            checkbox = mark_safe('<input type="checkbox" class="selected-commcare-case" data-bind="event: {change: updateCaseSelection}" data-formid="%(form_id)s" data-caseid="%(case_id)s" data-servicetype="%(service_type)s" data-domain="%(domain)s" />')
            amount_due = EMPTY_FIELD
            service_type = EMPTY_FIELD
            visits = form["form"].get("visits")
            form_id = form["form"]["meta"].get("instanceID")
            #location_name = EMPTY_FIELD
            #location_parent_name = EMPTY_FIELD

            #if case is not EMPTY_FIELD:
            #opened_by = get_property(case, "opened_by", EMPTY_FIELD)
            #owner = CommCareUser.get(opened_by)
            #location_id = get_property(owner, "location_id", EMPTY_FIELD)
            #location = Location.get(location_id)
            #location_name = get_property(location, "name", EMPTY_FIELD)
            #location_parent = get_property(location, "lineage", EMPTY_FIELD)[0]
            #location_parent_name = get_property(Location.get(location_parent), "name", EMPTY_FIELD)

            if "Immunization" in form["form"]["@name"]:
                service_type = _("Immunization")
                amount_due = 1000
            elif "DELIVERY" in form["form"]["@name"]:
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

            yield [
                DateTimeProperty().wrap(form["form"]["meta"]["timeEnd"]).strftime("%Y-%m-%d"),
                get_property(case, "full_name", EMPTY_FIELD),
                service_type,
                #location_name,
                get_property(case, "card_number", EMPTY_FIELD),
                #location_parent_name,
                get_property(case, "phone_number", EMPTY_FIELD),
                amount_due,
                checkbox % dict(form_id=form_id, case_id=case_id, service_type=service_type, domain=self.domain)
            ]

