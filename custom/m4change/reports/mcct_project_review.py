from datetime import date, datetime
from django.core.urlresolvers import reverse
from django.http import HttpResponse
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext as _
from jsonobject import DateTimeProperty

from corehq.apps.locations.models import Location
from corehq.apps.reports.filters.fixtures import AsyncLocationFilter
from corehq.elastic import ES_URLS
from corehq.apps.reports.standard import CustomProjectReport
from corehq.apps.reports.standard import ProjectReport, ProjectReportParametersMixin, DatespanMixin
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dont_use.fields import StrongFilterUsersField
from corehq.apps.reports.generic import ElasticProjectInspectionReport
from corehq.apps.reports.standard.monitoring import MultiFormDrilldownMixin
from corehq.elastic import es_query
from custom.m4change.constants import REJECTION_REASON_DISPLAY_NAMES, MCCT_SERVICE_TYPES
from custom.m4change.filters import ServiceTypeFilter
from custom.m4change.models import McctStatus
from custom.m4change.reports import get_location_hierarchy_by_id
from custom.m4change.utils import get_case_by_id, get_property, get_form_ids_by_status
from custom.m4change.constants import EMPTY_FIELD


def _get_date_range(range):
    if range is not None:
        dates = str(range).split(_(" to "))
        return (dates[0], dates[1])
    return None

def _get_relevant_xmlnss_for_service_type(service_type_filter):
    relevant_form_types = \
        MCCT_SERVICE_TYPES[service_type_filter] if service_type_filter else MCCT_SERVICE_TYPES["all"]
    return filter(None, [form for form in relevant_form_types])


def _get_report_query(start_date, end_date, filtered_case_ids, location_ids):
    return {
        "query": {
            "bool": {
                "must": [
                    {"range": {"form.meta.timeEnd": {"from": start_date, "to": end_date, "include_upper": True}}},
                    {"term": {"doc_type": "xforminstance"}}
                ]
            }
        },
        "filter": {
            "and": [
                {"not": {"missing": {"field": "form.case.@case_id"}}},
                {"terms": {"form.case.@case_id": filtered_case_ids}},
                {"script":{
                    "script": """
                    if (_source.form.?service_type != "" && _source.form.?location_id != "" && (location_ids contains _source.form.?location_id)) {
                        return true;
                    }
                    return false;
                    """,
                    "params": {
                        "location_ids": location_ids
                    }
                }}
            ]
        }
    }


def calculate_form_data(self, form):
    try:
        case_id = form["form"]["case"]["@case_id"]
        case = get_case_by_id(case_id)
    except KeyError:
        case = EMPTY_FIELD

    amount_due = EMPTY_FIELD
    if form["form"].get("registration_amount", None) is not None:
        amount_due = form["form"].get("registration_amount", None)
    elif form["form"].get("immunization_amount", None) is not None:
        amount_due = form["form"].get("immunization_amount", None)

    service_type = form["form"].get("service_type", EMPTY_FIELD)
    form_id = form["_id"]
    location_name = EMPTY_FIELD
    location_parent_name = EMPTY_FIELD
    location_id = form["form"].get("location_id", None)

    if location_id is not None:
        location = Location.get(location_id)
        location_name = location.name
        location_parent = location.parent
        if location_parent is not None and location_parent.location_type != 'state':
            while location_parent is not None and location_parent.location_type not in ('district', 'lga'):
                location_parent = location_parent.parent
        location_parent_name = location_parent.name if location_parent is not None else EMPTY_FIELD

    return {'case': case, 'service_type': service_type, 'location_name': location_name,
            'location_parent_name': location_parent_name, 'amount_due': amount_due, 'form_id': form_id}


class BaseReport(CustomProjectReport, ElasticProjectInspectionReport, ProjectReport,
                 ProjectReportParametersMixin, MultiFormDrilldownMixin, DatespanMixin):
        emailable = False
        exportable = True
        exportable_all = True
        asynchronous = True
        ajax_pagination = True
        include_inactive = True

        fields = [
            AsyncLocationFilter,
            'custom.m4change.fields.DateRangeField',
            'custom.m4change.fields.CaseSearchField',
            ServiceTypeFilter
        ]

        base_template = 'm4change/report.html'
        report_template_path = 'm4change/selectTemplate.html'
        filter_users_field_class = StrongFilterUsersField

        @property
        def es_results(self):
            if not getattr(self, 'es_response', None):
                self.es_query(paginated=True)
            return self.es_response

        @property
        def es_all_results(self):
            if not getattr(self, 'es_response', None):
                self.es_query(paginated=False)
            return self.es_response

        def _get_filtered_cases(self, start_date, end_date):
            query = {
                "query": {
                    "bool": {
                        "must_not": [
                            {"range": {"modified_on.date": {"lt": start_date}}},
                            {"range": {"opened_on.date": {"gt": end_date}}}
                        ]
                    }
                }
            }

            case_search = self.request.GET.get("case_search", "")
            if len(case_search) > 0:
                query["filter"] = {
                    "and": [
                        {"regexp": {"name.exact": ".*?%s.*?" % case_search}}
                    ]
                }

            es_response = es_query(params={"domain.exact": self.domain}, q=query, es_url=ES_URLS.get('cases'))
            return [res['_source']['_id'] for res in es_response.get('hits', {}).get('hits', [])]

        @property
        def total_records(self):
            return int(self.es_results['hits']['total'])

        def _make_link(self, url, label):
            return '<a href="%s" target="_blank">%s</a>' % (url, label)

        def _get_case_name_html(self, case, add_link):
            case_name = get_property(case, "full_name", EMPTY_FIELD)
            return self._make_link(
                reverse('corehq.apps.reports.views.case_details', args=[self.domain, case._id]), case_name
            ) if add_link else case_name

        def _get_service_type_html(self, form, service_type, add_link):
            return self._make_link(
                reverse('corehq.apps.reports.views.form_data', args=[self.domain, form['_id']]), service_type
            ) if add_link else service_type


class McctProjectReview(BaseReport):
    name = 'mCCT Beneficiary list view'
    slug = 'mcct_project_review_page'
    report_template_path = 'm4change/reviewStatus.html'
    display_status = 'eligible'

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Date of service"), prop_name="form.meta.timeEnd"),
            DataTablesColumn(_("Beneficiary Name"), sortable=False),
            DataTablesColumn(_("Service Type"), sortable=False),
            DataTablesColumn(_("Health Facility"), sortable=False),
            DataTablesColumn(_("Card No."), sortable=False),
            DataTablesColumn(_("LGA"), sortable=False),
            DataTablesColumn(_("Phone No."), sortable=False),
            DataTablesColumn(_("Amount"), sortable=False),
            DataTablesColumn(_("Visits"), sortable=False),
            DataTablesColumn(mark_safe('Status/Action  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> '
                                       '<a href="#" class="select-none btn btn-mini btn-warning">none</a>'),
                             sortable=False, span=3))
        return headers

    def es_query(self, paginated):
        if not getattr(self, 'es_response', None):
            range = self.request_params.get('range', None)
            start_date = None
            end_date = None
            if range is not None:
                dates = str(range).split(_(" to "))
                start_date = dates[0]
                end_date = dates[1]
            filtered_case_ids = self._get_filtered_cases(start_date, end_date)
            exclude_form_ids = [mcct_status.form_id for mcct_status in McctStatus.objects.filter(
                domain=self.domain, received_on__range=(start_date, end_date))
                                if (mcct_status.status != "eligible" or
                                    (mcct_status.immunized == False and
                                    (date.today() - mcct_status.registration_date).days < 272 and
                                     mcct_status.is_booking == False and mcct_status.is_stillbirth == False))]
            location_ids = get_location_hierarchy_by_id(self.request_params.get("location_id", None), self.domain,
                                                        CCT_only=True)
            q = _get_report_query(start_date, end_date, filtered_case_ids, location_ids)
            if len(exclude_form_ids) > 0:
                q["filter"]["and"].append({"not": {"ids": {"values": exclude_form_ids}}})

            xmlnss = _get_relevant_xmlnss_for_service_type(self.request.GET.get("service_type_filter"))
            if xmlnss:
                q["filter"]["and"].append({"terms": {"xmlns.exact": xmlnss}})

            modify_close = filter(None, [u'Modify/Close Client'])
            q["filter"]["and"].append({"not": {"terms": {"form.@name": modify_close}}})

            q["sort"] = self.get_sorting_block() \
                if self.get_sorting_block() else [{"form.meta.timeEnd" : {"order": "desc"}}]

            if paginated:
                self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'),
                                            start_at=self.pagination.start, size=self.pagination.count)
            else:
                self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'))
        return self.es_response

    @property
    def rows(self):
        return self.make_rows(self.es_results, with_checkbox=True)

    @property
    def get_all_rows(self):
        return self.make_rows(self.es_all_results, with_checkbox=False)

    def make_rows(self, es_results, with_checkbox):
        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]
        for form in submissions:
            data = calculate_form_data(self, form)
            row = [
                DateTimeProperty().wrap(form["form"]["meta"]["timeEnd"]).strftime("%Y-%m-%d"),
                self._get_case_name_html(data.get('case'), with_checkbox),
                self._get_service_type_html(form, data.get('service_type'), with_checkbox),
                data.get('location_name'),
                get_property(data.get('case'), "card_number", EMPTY_FIELD),
                data.get('location_parent_name'),
                get_property(data.get('case'), "phone_number", EMPTY_FIELD),
                data.get('amount_due'),
                get_property(data.get('case'), "visits", EMPTY_FIELD)
            ]
            if with_checkbox:
                checkbox = mark_safe('<input type="checkbox" class="selected-element" '
                                     'data-formid="%(form_id)s" '
                                     'data-caseid="%(case_id)s" data-servicetype="%(service_type)s"/>')
                row.append(checkbox % dict(form_id=data.get('form_id'), case_id=data.get('case_id'),
                                           service_type=data.get('service_type')))
            else:
                row.append(self.display_status)
            yield row

    @property
    def export_table(self):
        headers = self.headers
        headers.header.pop()
        headers.header.append(DataTablesColumn(_("Status"), sortable=False))
        table = headers.as_export_table
        export_rows = self.get_all_rows
        table.extend(export_rows)
        return [[self.export_sheet_name, table]]


class McctClientApprovalPage(McctProjectReview):
    name = 'mCCT Beneficiary Approval Page'
    slug = 'mcct_client_approval_page'
    report_template_path = 'm4change/approveStatus.html'
    display_status = 'reviewed'

    def es_query(self, paginated):
        reviewed_form_ids = get_form_ids_by_status(self.domain, getattr(self, 'display_status', None))
        if len(reviewed_form_ids) > 0:
            if not getattr(self, 'es_response', None):
                date_tuple = _get_date_range(self.request_params.get('range', None))
                filtered_case_ids = self._get_filtered_cases(date_tuple[0], date_tuple[1])
                location_ids = get_location_hierarchy_by_id(self.request_params.get("location_id", None), self.domain,
                                                            CCT_only=True)
                q = _get_report_query(date_tuple[0], date_tuple[1], filtered_case_ids, location_ids)

                if len(reviewed_form_ids) > 0:
                    q["filter"]["and"].append({"ids": {"values": reviewed_form_ids}})

                q["sort"] = self.get_sorting_block() if self.get_sorting_block() else [{"form.meta.timeEnd" : {"order": "desc"}}]
                if paginated:
                    self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'),
                                                start_at=self.pagination.start, size=self.pagination.count)
                else:
                    self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'))
        else:
            self.es_response = {'hits': {'total': 0}}

        return self.es_response


class McctClientPaymentPage(McctClientApprovalPage):
    name = 'mCCT Beneficiary Payment Page'
    slug = 'mcct_client_payment_page'
    report_template_path = 'm4change/paidStatus.html'
    display_status = 'approved'


class McctRejectedClientPage(McctClientApprovalPage):
    name = 'mCCT Rejected Beneficiary Page'
    slug = 'mcct_rejected_clients_page'
    report_template_path = 'm4change/activateStatus.html'
    display_status = 'rejected'

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Date of service"), prop_name="form.meta.timeEnd"),
            DataTablesColumn(_("Beneficiary Name"), sortable=False),
            DataTablesColumn(_("Service Type"), sortable=False),
            DataTablesColumn(_("Health Facility"), sortable=False),
            DataTablesColumn(_("Card No."), sortable=False),
            DataTablesColumn(_("LGA"), sortable=False),
            DataTablesColumn(_("Phone No."), sortable=False),
            DataTablesColumn(_("Amount"), sortable=False),
            DataTablesColumn(_("Comment"), sortable=False),
            DataTablesColumn(_("User"), sortable=False),
            DataTablesColumn(mark_safe('Status/Action  <a href="#" class="select-all btn btn-mini btn-inverse">all</a> '
                                       '<a href="#" class="select-none btn btn-mini btn-warning">none</a>'),
                             sortable=False, span=3))
        return headers

    def make_rows(self, es_results, with_checkbox):
        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]
        for form in submissions:
            data = calculate_form_data(self, form)
            try:
                status_data = McctStatus.objects.get(domain=self.domain, form_id=data.get('form_id'))
                reason = status_data.reason
            except McctStatus.DoesNotExist:
                reason = None
            row = [
                DateTimeProperty().wrap(form["form"]["meta"]["timeEnd"]).strftime("%Y-%m-%d %H:%M"),
                self._get_case_name_html(data.get('case'), with_checkbox),
                self._get_service_type_html(form, data.get('service_type'), with_checkbox),
                data.get('location_name'),
                get_property(data.get('case'), "card_number", EMPTY_FIELD),
                data.get('location_parent_name'),
                get_property(data.get('case'), "phone_number", EMPTY_FIELD),
                data.get('amount_due'),
                REJECTION_REASON_DISPLAY_NAMES[reason] if reason is not None else '',
                form["form"]["meta"]["username"]
            ]
            if with_checkbox:
                checkbox = mark_safe('<input type="checkbox" class="selected-element" '
                                     'data-formid="%(form_id)s" '
                                     'data-caseid="%(case_id)s" data-servicetype="%(service_type)s"/>')
                row.append(checkbox % dict(form_id=data.get('form_id'), case_id=data.get('case_id'),
                                           service_type=data.get('service_type')))
            else:
                row.insert(8, self.display_status)
            yield row

    @property
    def export_table(self):
        headers = self.headers
        headers.header.insert(8, DataTablesColumn("Status", sortable=False))
        headers.header.pop()
        table = headers.as_export_table
        export_rows = self.get_all_rows
        table.extend(export_rows)
        return [[self.export_sheet_name, table]]


class McctClientLogPage(McctProjectReview):
    name = 'mCCT Beneficiary Log Page'
    slug = 'mcct_client_log_page'
    report_template_path = 'm4change/report_content.html'

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Date of action"), sortable=False),
            DataTablesColumn(_("Beneficiary Name"), sortable=False),
            DataTablesColumn(_("Service Type"), sortable=False),
            DataTablesColumn(_("Health Facility"), sortable=False),
            DataTablesColumn(_("Card No."), sortable=False),
            DataTablesColumn(_("LGA"), sortable=False),
            DataTablesColumn(_("Phone No."), sortable=False),
            DataTablesColumn(_("Amount"), sortable=False),
            DataTablesColumn(_("Status"), sortable=False),
            DataTablesColumn(_("Comment"), sortable=False),
            DataTablesColumn(_("User"), sortable=False))
        return headers

    def es_query(self, paginated):
        if not getattr(self, 'es_response', None):
            date_tuple = _get_date_range(self.request_params.get('range', None))
            filtered_case_ids = self._get_filtered_cases(date_tuple[0], date_tuple[1])
            location_ids = get_location_hierarchy_by_id(self.request_params.get("location_id", None), self.domain,
                                                        CCT_only=True)
            q = _get_report_query(date_tuple[0], date_tuple[1], filtered_case_ids, location_ids)

            xmlnss = _get_relevant_xmlnss_for_service_type(self.request.GET.get("service_type_filter"))
            if xmlnss:
                q["filter"]["and"].append({"terms": {"xmlns.exact": xmlnss}})

            modify_close = filter(None, [u'Modify/Close Client'])
            q["filter"]["and"].append({"not": {"terms": {"form.@name": modify_close}}})

            q["sort"] = self.get_sorting_block() \
                if self.get_sorting_block() else [{"form.meta.timeEnd": {"order": "desc"}}]
            if paginated:
                self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'),
                                            start_at=self.pagination.start, size=self.pagination.count)
            else:
                self.es_response = es_query(params={"domain.exact": self.domain}, q=q, es_url=ES_URLS.get('forms'))
        return self.es_response

    def make_rows(self, es_results, with_checkbox):
        submissions = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]
        for form in submissions:
            data = calculate_form_data(self, form)
            try:
                status_data = McctStatus.objects.get(domain=self.domain, form_id=data.get('form_id'))
                status, reason, status_date, username = (status_data.status, status_data.reason,
                                                         status_data.modified_on, status_data.user)
            except:
                status, reason, status_date, username = ('eligible', None, None, None)
            row = [
                status_date.strftime("%Y-%m-%d %H:%M") if status_date is not None else EMPTY_FIELD,
                self._get_case_name_html(data.get('case'), with_checkbox),
                self._get_service_type_html(form, data.get('service_type'), with_checkbox),
                data.get('location_name'),
                get_property(data.get('case'), "card_number", EMPTY_FIELD),
                data.get('location_parent_name'),
                get_property(data.get('case'), "phone_number", EMPTY_FIELD),
                data.get('amount_due'),
                status,
                REJECTION_REASON_DISPLAY_NAMES[reason] if reason is not None else '',
                username if username else form["form"]["meta"]["username"]
            ]
            yield row

    @property
    def export_table(self):
        table = self.headers.as_export_table
        export_rows = self.get_all_rows
        table.extend(export_rows)
        return [[self.export_sheet_name, table]]


class McctPaidClientsPage(McctClientApprovalPage):
    name = 'mCCT Paid Beneficiary Page'
    slug = 'mcct_paid_clients_page'
    report_template_path = 'm4change/report_content.html'
    display_status = 'paid'

    @property
    def rows(self):
        return self.make_rows(self.es_results, with_checkbox=False)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Date of service"), prop_name="form.meta.timeEnd"),
            DataTablesColumn(_("Beneficiary Name"), sortable=False),
            DataTablesColumn(_("Service Type"), sortable=False),
            DataTablesColumn(_("Health Facility"), sortable=False),
            DataTablesColumn(_("Card No."), sortable=False),
            DataTablesColumn(_("LGA"), sortable=False),
            DataTablesColumn(_("Phone No."), sortable=False),
            DataTablesColumn(_("Amount"), sortable=False),
            DataTablesColumn(_("Status"), sortable=False))
        return headers
