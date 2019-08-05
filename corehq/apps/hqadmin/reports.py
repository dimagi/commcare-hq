from __future__ import absolute_import
from __future__ import unicode_literals
import copy
from datetime import datetime, timedelta
import json

from django.urls import reverse

from auditcare.models import NavigationEventAudit
from auditcare.utils.export import navigation_event_ids_by_user
from corehq.apps.builds.utils import get_all_versions
from corehq.apps.es import FormES, filters, UserES
from corehq.apps.es.aggregations import NestedTermAggregationsHelper, AggregationTerm, SumAggregation
from corehq.apps.hqwebapp.decorators import (
    use_nvd3,
)
from corehq.apps.reports.standard import DatespanMixin
from dimagi.utils.couch.database import iter_docs
from memoized import memoized
from corehq.apps.accounting.models import (
    SoftwarePlanEdition,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import ElasticTabularReport, GenericTabularReport
from corehq.apps.reports.standard.domains import DomainStatsReport, es_domain_query
from corehq.apps.reports.standard.sms import PhoneNumberReport
from corehq.apps.sms.filters import RequiredPhoneNumberFilter
from corehq.apps.sms.mixin import apply_leniency
from corehq.apps.sms.models import PhoneNumber
from django.utils.translation import ugettext as _, ugettext_noop, ugettext_lazy
from corehq.elastic import es_query, parse_args_for_es, fill_mapping_with_facets
from corehq.apps.app_manager.commcare_settings import get_custom_commcare_settings
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from corehq.util.python_compatibility import soft_assert_type_text
from phonelog.reports import BaseDeviceLogReport
from phonelog.models import DeviceReportEntry
from corehq.apps.es.domains import DomainES
import six
from six.moves import range

INDICATOR_DATA = {
    "active_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_domains",
        "chart_title": "Active Project Spaces (last 30 days)",
        "hide_cumulative_charts": True,
        "histogram_type": "active_domains",
        "xaxis_label": "# domains",
    },
    "active_domain_count_forms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_domain_count_forms",
        "chart_title": "Active Project Spaces (via Mobile Worker) (last 30 days)",
        "get_request_params": {
            "add_sms_domains": False,
            "restrict_to_mobile_submissions": True,
        },
        "hide_cumulative_charts": True,
        "histogram_type": "active_domains",
        "xaxis_label": "# domains",
    },
    "active_domain_count_sms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_domain_count_sms",
        "chart_title": "Active Project Spaces (via SMS) (last 30 days)",
        "get_request_params": {
            "add_form_domains": False,
        },
        "hide_cumulative_charts": True,
        "histogram_type": "active_domains",
        "xaxis_label": "# domains",
    },
    "active_community_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_community_domain_count",
        "chart_title": "Active Community Project Spaces (last 30 days)",
        "get_request_params": {
            "software_plan_edition": SoftwarePlanEdition.COMMUNITY,
        },
        "hide_cumulative_charts": True,
        "histogram_type": "active_domains",
        "xaxis_label": "# domains",
    },
    "active_self_started_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_self_started_domains",
        "chart_title": "Active Self Started Project Spaces (last 30 days)",
        "get_request_params": {
            "domain_params_es": {
                "internal.self_started": ["T"],
            },
        },
        "hide_cumulative_charts": True,
        "histogram_type": "active_domains",
        "xaxis_label": "# domains",
    },
    "domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "domains",
        "chart_title": "Total Project Spaces",
        "histogram_type": "domains",
        "xaxis_label": "# domains",
    },
    "commtrack_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "domains",
        "chart_title": "Total CommCare Supply Project Spaces",
        "histogram_type": "domains",
        "xaxis_label": "# domains",
    },
    "domain_self_started_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "self_started_domains",
        "chart_title": "Total Self-Started Project Spaces",
        "get_request_params": {
            "domain_params_es": {
                "internal.self_started": ["T"],
            },
        },
        "histogram_type": "domains",
        "xaxis_label": "# domains",
    },
    "subscriptions": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "subscriptions",
        "chart_title": "Subscriptions",
        "hide_cumulative_charts": True,
        "histogram_type": "subscriptions",
        "is_cumulative": False,
        "xaxis_label": "# domains on subscription",
    },
    "forms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "forms",
        "chart_title": "Forms Submitted by All Users",
        "histogram_type": "forms",
        "xaxis_label": "# forms",
    },
    "forms_mobile": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "forms_mobile",
        "chart_title": "Forms Submitted by Mobile Workers",
        "get_request_params": {
            "user_type_mobile": True,
        },
        "histogram_type": "forms",
        "xaxis_label": "# forms",
    },
    "forms_web": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "forms_web",
        "chart_title": "Forms Submitted by Web Users",
        "get_request_params": {
            "user_type_mobile": False,
        },
        "histogram_type": "forms",
        "xaxis_label": "# forms",
    },
    "forms_j2me": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "forms_j2me",
        "chart_title": "J2ME Forms Submitted",
        "get_request_params": {
            "j2me_only": True,
        },
        "histogram_type": "forms",
        "xaxis_label": "# forms",
    },
    "users": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "users",
        "chart_title": "Total Users",
        "histogram_type": "users_all",
        "xaxis_label": "# users",
    },
    "users_mobile": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "users_mobile",
        "chart_title": "Mobile Users Who Have Submitted a Form",
        "get_request_params": {
            "user_type_mobile": True,
        },
        "histogram_type": "users_all",
        "xaxis_label": "# users",
    },
    "users_web": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "users_web",
        "chart_title": "Web Users Who Have Submitted A Form",
        "get_request_params": {
            "user_type_mobile": False,
        },
        "histogram_type": "users_all",
        "xaxis_label": "# users",
    },
    "commtrack_users_web": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "commtrack_users_web",
        "chart_title": "CommCare Supply Web Users",
        "get_request_params": {
            "require_submissions": False,
            "user_type_mobile": False,
        },
        "histogram_type": "users_all",
        "xaxis_label": "# users",
    },
    "active_users_mobile": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_users_mobile",
        "chart_title": "Active Mobile Users (last 30 days)",
        "get_request_params": {
            "include_forms": True,
            "additional_params_es": {
                "couch_recipient_doc_type": ["commcareuser"],
            },
        },
        "hide_cumulative_charts": True,
        "histogram_type": "active_mobile_users",
        "is_cumulative": False,
        "xaxis_label": "# users",
    },
    "active_cases": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_cases",
        "chart_title": "Active Cases (last 90 days)",
        "hide_cumulative_charts": True,
        "histogram_type": "active_cases",
        "is_cumulative": False,
        "xaxis_label": "# cases",
    },
    "sms_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "sms_domains",
        "chart_title": "Total Projects That Have Used SMS",
        "histogram_type": "sms_domains",
        "xaxis_label": "# domains",
    },
    "commconnect_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "commconnect_domains",
        "chart_title": "Total Domains That Use Messaging",
        "histogram_type": "domains",
        "xaxis_label": "# domains",
    },
    "incoming_sms_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "incoming_sms_domains",
        "chart_title": "Total Projects That Have Used Incoming SMS",
        "get_request_params": {
            "additional_params_es": {
                "direction": ["i"],
            },
        },
        "histogram_type": "sms_domains",
        "xaxis_label": "# domains",
    },
    "sms_only_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "sms_only_domains",
        "chart_title": "Total Projects Using Only SMS",
        "histogram_type": "sms_only_domains",
        "xaxis_label": "# domains",
    },
    "active_commconnect_domain_count": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_commconnect_domains",
        "chart_title": "Active Project Spaces That Use Messaging (last 30 days)",
        "get_request_params": {
            "add_form_domains": False,
        },
        "hide_cumulative_charts": True,
        "histogram_type": "active_domains",
        "xaxis_label": "# domains",
    },
    "total_outgoing_sms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "total_outgoing_sms",
        "chart_title": "Total SMS Sent By A Project",
        "get_request_params": {
            "additional_params_es": {
                "direction": ["o"],
            },
        },
        "histogram_type": "real_sms_messages",
        "xaxis_label": "# domains",
    },
    "total_incoming_sms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "total_incoming_sms",
        "chart_title": "Total SMS Received By A Project",
        "get_request_params": {
            "additional_params_es": {
                "direction": ["i"],
            },
        },
        "histogram_type": "real_sms_messages",
        "xaxis_label": "# domains",
    },
    "total_outgoing_client_sms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "total_outgoing_client_sms",
        "chart_title": "Total SMS Sent To A Client",
        "get_request_params": {
            "additional_params_es": {
                "direction": ["o"],
                "couch_recipient_doc_type": ["commcarecase"],
            },
        },
        "histogram_type": "real_sms_messages",
        "xaxis_label": "# domains",
    },
    "total_incoming_client_sms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "total_incoming_client_sms",
        "chart_title": "Total SMS Sent From A Client",
        "get_request_params": {
            "additional_params_es": {
                "direction": ["i"],
                "couch_recipient_doc_type": ["commcarecase"],
            },
        },
        "histogram_type": "real_sms_messages",
        "xaxis_label": "# domains",
    },
    "total_mobile_workers": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "total_mobile_workers",
        "chart_title": "Total Mobile Workers",
        "histogram_type": "mobile_workers",
        "xaxis_label": "# workers",
    },
    "active_mobile_workers": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_mobile_workers",
        "chart_title": "Active Mobile Workers (last 30 days)",
        "get_request_params": {
            "additional_params_es": {
                "couch_recipient_doc_type": ["commcareuser"],
            },
        },
        "hide_cumulative_charts": True,
        "histogram_type": "active_mobile_users",
        "xaxis_label": "# workers",
    },
    "active_dimagi_owned_gateways": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_dimagi_owned_gateways",
        "chart_title": "Active Projects Using Dimagi Owned Gateways (last 30 days)",
        "hide_cumulative_charts": True,
        "histogram_type": "active_dimagi_gateways",
        "xaxis_label": "# domains",
    },
    "total_clients": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "total_clients",
        "chart_title": "Total Mobile Clients",
        "histogram_type": "mobile_clients",
        "xaxis_label": "# workers",
    },
    "active_clients": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_mobile_clients",
        "chart_title": "Active Mobile Clients (last 30 days)",
        "hide_cumulative_charts": True,
        "get_request_params": {
            "additional_params_es": {
                "couch_recipient_doc_type": ["commcarecase"],
            },
        },
        "histogram_type": "active_mobile_users",
        "xaxis_label": "# workers",
    },
    "active_countries": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_countries",
        "chart_title": "Active Countries",
        "hide_cumulative_charts": True,
        "histogram_type": "active_countries",
        "xaxis_label": "# countries",
    },
    "countries": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "countries",
        "chart_title": "Total Countries",
        "hide_cumulative_charts": True,
        "histogram_type": "countries",
        "xaxis_label": "# countries",
    },
    "commtrack_total_outgoing_sms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "commtrack_total_outgoing_sms",
        "chart_title": "Total Outgoing CommCare Supply SMS",
        "get_request_params": {
            "additional_params_es": {
                "direction": ["o"],
            },
            "is_commtrack": True,
        },
        "histogram_type": "real_sms_messages",
        "xaxis_label": "# SMS",
    },
    "commtrack_total_incoming_sms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "commtrack_total_incoming_sms",
        "chart_title": "Total Incoming CommCare Supply SMS",
        "get_request_params": {
            "additional_params_es": {
                "direction": ["i"],
            },
            "is_commtrack": True,
        },
        "histogram_type": "real_sms_messages",
        "xaxis_label": "# SMS",
    },
    "commtrack_forms": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "commtrack_forms",
        "chart_title": "Total CommCare Supply Form Submissions",
        "histogram_type": "commtrack_forms",
        "xaxis_label": "# forms",
    },
    "active_supply_points": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "active_supply_points",
        "chart_title": "Active Supply Points (last 90 days)",
        "hide_cumulative_charts": True,
        "histogram_type": "active_supply_points",
        "is_cumulative": False,
        "xaxis_label": "# supply points",
    },
    "total_products": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "total_products",
        "chart_title": "Number of Products",
        "hide_cumulative_charts": False,
        "histogram_type": "total_products",
        "interval": "month",
        "is_cumulative": False,
        "xaxis_label": "# products",
    },
    "stock_transactions": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "stock_transactions",
        "chart_title": "Total Stock Transactions",
        "histogram_type": "stock_transactions",
        "xaxis_label": "# stock transactions",
    },
    "unique_locations": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "unique_locations",
        "chart_title": "Unique Locations",
        "histogram_type": "unique_locations",
        "xaxis_label": "# unique locations",
    },
    "location_types": {
        "ajax_view": "admin_reports_stats_data",
        "chart_name": "location_types",
        "chart_title": "Types of Locations",
        "histogram_type": "location_types",
        "xaxis_label": "# location types",
    },
}

ES_PREFIX = "es_"

DOMAIN_FACETS = [
    "cp_is_active",
    "cp_has_app",
    "cp_sms_ever",
    "cp_sms_30_d",
    "uses reminders",
    "project_type",
    "area",
    "case_sharing",
    "customer_type",
    "deployment.city.exact",
    "deployment.countries.exact",
    "deployment.public",
    "deployment.region.exact",
    "hr_name",
    "internal.area.exact",
    "internal.can_use_data",
    "internal.custom_eula",
    "internal.initiative.exact",
    "internal.workshop_region.exact",
    "internal.project_state",
    "internal.self_started",
    "internal.sf_account_id",
    "internal.sf_contract_id",
    "internal.sub_area.exact",
    "internal.using_adm",
    "internal.using_call_center",
    "internal.platform",
    "internal.project_manager",
    "internal.phone_model.exact",
    "internal.commtrack_domain",

    "is_approved",
    "is_shared",
    "is_sms_billable",
    "is_snapshot",
    "is_test",
    "license",
    "multimedia_included",

    "phone_model",
    "published",
    "sub_area",
    "survey_management_enabled",
    "use_sql_backend",
    "tags",
]

FACET_MAPPING = [
    ("Activity", True, [
        {"facet": "is_test", "name": "Test Project", "expanded": True},
        {"facet": "cp_is_active", "name": "Active", "expanded": True},
        {"facet": "internal.project_state", "name": "Scale", "expanded": False},
    ]),
    ("Location", True, [
        {"facet": "deployment.countries.exact", "name": "Country", "expanded": True},
        {"facet": "deployment.region.exact", "name": "Region", "expanded": False},
        {"facet": "deployment.city.exact", "name": "City", "expanded": False},
        {"facet": "internal.workshop_region.exact", "name": "Workshop Region", "expanded": False},
    ]),
    ("Type", True, [
        {"facet": "internal.area.exact", "name": "Sector", "expanded": True},
        {"facet": "internal.sub_area.exact", "name": "Sub-Sector", "expanded": True},
        {"facet": "internal.phone_model.exact", "name": "Phone Model", "expanded": True},
        {"facet": "internal.project_manager", "name": "Project Manager", "expanded": True},
    ]),
    ("Self Starters", False, [
        {"facet": "internal.self_started", "name": "Self Started", "expanded": True},
        {"facet": "cp_has_app", "name": "Has App", "expanded": False},
    ]),
    ("Advanced Features", False, [
        # {"facet": "", "name": "Reminders", "expanded": True },
        {"facet": "case_sharing", "name": "Case Sharing", "expanded": False},
        {"facet": "internal.using_adm", "name": "ADM", "expanded": False},
        {"facet": "internal.using_call_center", "name": "Call Center", "expanded": False},
        {"facet": "internal.commtrack_domain", "name": "CommCare Supply", "expanded": False},
        {"facet": "survey_management_enabled", "name": "Survey Management", "expanded": False},
        {"facet": "cp_sms_ever", "name": "Used Messaging Ever", "expanded": False},
        {"facet": "cp_sms_30_d", "name": "Used Messaging Last 30 days", "expanded": False},
        {"facet": "use_sql_backend", "name": "Uses 'scale' backend", "expanded": False},
    ]),
    ("Plans", False, [
        {"facet": "project_type", "name": "Project Type", "expanded": False},
        {"facet": "customer_type", "name": "Customer Type", "expanded": False},
        {"facet": "internal.initiative.exact", "name": "Initiative", "expanded": False},
        {"facet": "is_sms_billable", "name": "SMS Billable", "expanded": False},
    ]),
    ("Eula", False, [
        {"facet": "internal.can_use_data", "name": "Public Data", "expanded": True},
        {"facet": "internal.custom_eula", "name": "Custom Eula", "expanded": True},
    ]),
]

class AdminReport(GenericTabularReport):
    dispatcher = AdminReportDispatcher

    base_template = "hqadmin/faceted_report.html"
    report_template_path = "reports/tabular.html"
    section_name = ugettext_noop("ADMINREPORT")
    default_params = {}
    is_admin_report = True


class AdminFacetedReport(AdminReport, ElasticTabularReport):
    default_sort = None
    es_prefix = "es_"  # facet keywords in the url will be prefixed with this
    asynchronous = False
    ajax_pagination = True
    exportable = True
    es_queried = False
    es_facet_list = []
    es_facet_mapping = []
    es_index = None
    es_search_fields = ["_all"]

    @property
    def template_context(self):
        ctxt = super(AdminFacetedReport, self).template_context

        self.run_query(0)
        if self.es_params.get('search'):
            ctxt["search_query"] = self.es_params.get('search')[0]
        ctxt.update({
            'layout_flush_content': True,
            'facet_map': self.es_facet_map,
            'query_str': self.request.META['QUERY_STRING'],
            'facet_prefix': self.es_prefix,
            'facet_report': self,
            'grouped_facets': True,
            'startdate': self.request.GET.get('startdate', ''),
            'enddate': self.request.GET.get('enddate', ''),
            'interval': self.request.GET.get('interval', ''),
        })
        return ctxt

    @property
    def total_records(self):
        return int(self.es_results['hits']['total'])

    def is_custom_param(self, param):
        return param.startswith(self.es_prefix)

    @property
    def shared_pagination_GET_params(self):
        ret = super(AdminFacetedReport, self).shared_pagination_GET_params
        for param in six.iterlists(self.request.GET):
            if self.is_custom_param(param[0]):
                for val in param[1]:
                    ret.append(dict(name=param[0], value=val))
        return ret

    def es_query(self, params=None, size=None):
        if params is None:
            params = {}
        terms = ['search']
        q = {"query": {"match_all": {}}}

        search_query = params.get('search', "")
        if search_query:
            q['query'] = {
                "bool": {
                    "must": {
                        "multi_match": {
                            "query": search_query,
                            "operator": "and",
                            "fields": self.es_search_fields,
                        }}}}

        q["facets"] = {}

        q["sort"] = self.get_sorting_block()
        start_at = self.pagination.start
        size = size if size is not None else self.pagination.count
        return es_query(params, self.es_facet_list, terms, q, self.es_index, start_at, size, facet_size=25)

    @property
    def es_results(self):
        if not self.es_queried:
            self.run_query()
        return self.es_response

    def run_query(self, size=None):
        self.es_params, _ = parse_args_for_es(self.request, prefix=self.es_prefix)
        results = self.es_query(self.es_params, size)
        self.es_facet_map = fill_mapping_with_facets(self.es_facet_mapping, results, self.es_params)
        self.es_response = results
        self.es_queried = True
        return self.es_response

    @property
    def export_table(self):
        self.pagination.count = 1000000  # terrible hack to get the export to return all rows
        self.show_name = True
        return super(AdminFacetedReport, self).export_table


class AdminDomainStatsReport(AdminFacetedReport, DomainStatsReport):
    slug = "domains"
    es_facet_list = DOMAIN_FACETS
    es_facet_mapping = FACET_MAPPING
    name = ugettext_noop('Project Space List')
    facet_title = ugettext_noop("Project Facets")
    search_for = ugettext_noop("projects...")
    base_template = "hqadmin/domain_faceted_report.html"

    @use_nvd3
    def decorator_dispatcher(self, request, *args, **kwargs):
        super(AdminDomainStatsReport, self).decorator_dispatcher(request, *args, **kwargs)

    @property
    def template_context(self):
        ctxt = super(AdminDomainStatsReport, self).template_context
        ctxt["interval"] = "week"

        ctxt["domain_datefields"] = [
            {"value": "date_created", "name": _("Date Created")},
            {"value": "cp_first_form", "name": _("First Form Submitted")},
            {"value": "cp_last_form", "name": _("Last Form Submitted")},
        ]
        return ctxt

    def es_query(self, params=None, size=None):
        size = size if size is not None else self.pagination.count
        return es_domain_query(params, self.es_facet_list, sort=self.get_sorting_block(),
                               start_at=self.pagination.start, size=size)

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Project"), prop_name="name.exact"),
            DataTablesColumn(_("Date Created"), prop_name="date_created"),
            DataTablesColumn(_("Organization"), prop_name="internal.organization_name.exact"),
            DataTablesColumn(_("Deployment Country"), prop_name="deployment.countries.exact"),
            DataTablesColumn(_("# Active Mobile Workers"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_active_cc_users",
                help_text=_("the number of mobile workers who have submitted a form or an SMS in the last 30 days. "
                            "Includes deactivated workers.")),
            DataTablesColumn(_("# Mobile Workers"), sort_type=DTSortType.NUMERIC,
                             prop_name="cp_n_cc_users",
                             help_text=_("Does not include deactivated users.")),
            DataTablesColumn(_("# Mobile Workers (Submitted Form)"), sort_type=DTSortType.NUMERIC,
                             prop_name="cp_n_users_submitted_form",
                             help_text=_("Includes deactivated workers.")),
            DataTablesColumn(_("# Cases in last 60"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_60_day_cases",
                help_text=_("The number of *currently open* cases created or updated in the last 60 days")),
            DataTablesColumn(_("# Active Cases"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_active_cases",
                help_text=_("The number of *currently open* cases created or updated in the last 120 days")),
            DataTablesColumn(_("# Inactive Cases"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_inactive_cases",
                help_text=_("The number of open cases not created or updated in the last 120 days")),
            DataTablesColumn(_("# Cases"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_cases"),
            DataTablesColumn(_("# Form Submissions"), sort_type=DTSortType.NUMERIC, prop_name="cp_n_forms"),
            DataTablesColumn(_("# Form Submissions in last 30 days"), sort_type=DTSortType.NUMERIC,
                             prop_name="cp_n_forms_30_d"),
            DataTablesColumn(_("First Form Submission"), prop_name="cp_first_form"),
            DataTablesColumn(_("300th Form Submission"), prop_name="cp_300th_form"),
            DataTablesColumn(_("Last Form Submission"), prop_name="cp_last_form"),
            DataTablesColumn(_("# Web Users"), sort_type=DTSortType.NUMERIC,
                             prop_name="cp_n_web_users",
                             help_text=_("Does not include deactivated users.")),
            DataTablesColumn(_("Notes"), prop_name="internal.notes"),
            DataTablesColumn(_("Project State"), prop_name="internal.project_state"),
            DataTablesColumn(_("Using ADM?"), prop_name="internal.using_adm"),
            DataTablesColumn(_("Using Call Center?"), prop_name="internal.using_call_center"),
            DataTablesColumn(_("Date Last Updated"), prop_name="cp_last_updated",
                help_text=_("The time when these indicators were last calculated")),
            DataTablesColumn(_("Sector"), prop_name="internal.area.exact"),
            DataTablesColumn(_("Sub-Sector"), prop_name="internal.sub_area.exact"),
            DataTablesColumn(_("Business Unit"), prop_name="internal.business_unit.exact"),
            DataTablesColumn(_("Self-Starter?"), prop_name="internal.self_started"),
            DataTablesColumn(_("Test Project?"), prop_name="is_test"),
            DataTablesColumn(_("Active?"), prop_name="cp_is_active"),
            DataTablesColumn(_("CommCare Supply?"), prop_name="internal.commtrack_domain"),
            DataTablesColumn(_("# Outgoing SMS"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_out_sms"),
            DataTablesColumn(_("# Incoming SMS"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_in_sms"),
            DataTablesColumn(_("# SMS Ever"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_sms_ever"),
            DataTablesColumn(_("# Incoming SMS in last 30 days"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_sms_in_30_d"),
            DataTablesColumn(_("# Outgoing SMS in last 30 days"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_sms_out_30_d"),
            DataTablesColumn(_("Custom EULA?"), prop_name="internal.custom_eula"),
            DataTablesColumn(_("HIPAA Compliant"), prop_name="hipaa_compliant"),
            DataTablesColumn(_("Has J2ME submission in past 90 days"), prop_name="cp_j2me_90_d_bool"),
        )
        return headers

    @property
    def rows(self):
        domains = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        def get_from_stat_facets(prop, what_to_get):
            return self.es_results.get('facets', {}).get('%s-STATS' % prop, {}).get(what_to_get)

        CALCS_ROW_INDEX = {
            4: "cp_n_active_cc_users",
            5: "cp_n_cc_users",
            6: "cp_n_users_submitted_form",
            7: "cp_n_60_day_cases",
            8: "cp_n_active_cases",
            9: "cp_n_inactive_cases",
            10: "cp_n_cases",
            11: "cp_n_forms",
            12: "cp_n_forms_30_d",
            16: "cp_n_web_users",
            28: "cp_n_out_sms",
            29: "cp_n_in_sms",
            30: "cp_n_sms_ever",
            31: "cp_n_sms_in_30_d",
            32: "cp_n_sms_out_30_d",
            33: "cp_j2me_90_d_bool",
        }

        def stat_row(name, what_to_get, type='float'):
            row = [name]
            for index in range(1, len(self.headers)):
                if index in CALCS_ROW_INDEX:
                    val = get_from_stat_facets(CALCS_ROW_INDEX[index], what_to_get)
                    row.append('%.2f' % float(val) if val and type=='float' else val or "Not yet calculated")
                else:
                    row.append('---')
            return row

        self.total_row = stat_row(_('Total'), 'total', type='int')
        self.statistics_rows = [
            stat_row(_('Mean'), 'mean'),
            stat_row(_('STD'), 'std_deviation'),
        ]

        def format_date(dstr, default):
            # use [:19] so that only only the 'YYYY-MM-DDTHH:MM:SS' part of the string is parsed
            return datetime.strptime(dstr[:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y/%m/%d %H:%M:%S') if dstr else default

        def format_bool(val):
            if isinstance(val, bool):
                return "{}".format(val)
            return _('No info')

        for dom in domains:
            if 'name' in dom:  # for some reason when using the statistical facet, ES adds an empty dict to hits
                first_form_default_message = _("No Forms")
                if dom.get("cp_last_form", None):
                    first_form_default_message = _("Unable to parse date")

                yield [
                    self.get_name_or_link(dom, internal_settings=True),
                    format_date((dom.get("date_created")), _('No date')),
                    dom.get("internal", {}).get('organization_name') or _('No org'),
                    (dom.get("deployment") or {}).get('countries') or _('No countries'),
                    dom.get("cp_n_active_cc_users", _("Not yet calculated")),
                    dom.get("cp_n_cc_users", _("Not yet calculated")),
                    dom.get("cp_n_users_submitted_form", _("Not yet calculated")),
                    dom.get("cp_n_60_day_cases", _("Not yet calculated")),
                    dom.get("cp_n_active_cases", _("Not yet calculated")),
                    dom.get("cp_n_inactive_cases", _("Not yet calculated")),
                    dom.get("cp_n_cases", _("Not yet calculated")),
                    dom.get("cp_n_forms", _("Not yet calculated")),
                    dom.get("cp_n_forms_30_d", _("Not yet calculated")),
                    format_date(dom.get("cp_first_form"), first_form_default_message),
                    format_date(dom.get('cp_300th_form'), _('No 300th form')),
                    format_date(dom.get("cp_last_form"), _("No forms")),
                    dom.get("cp_n_web_users", _("Not yet calculated")),
                    dom.get('internal', {}).get('notes') or _('No notes'),
                    dom.get('internal', {}).get('project_state') or _('No info'),
                    format_bool(dom.get('internal', {}).get('using_adm')),
                    format_bool(dom.get('internal', {}).get('using_call_center')),
                    format_date(dom.get("cp_last_updated"), _("No Info")),
                    dom.get('internal', {}).get('area') or _('No info'),
                    dom.get('internal', {}).get('sub_area') or _('No info'),
                    dom.get('internal', {}).get('business_unit') or _('No info'),
                    format_bool(dom.get('internal', {}).get('self_started')),
                    dom.get('is_test') or _('No info'),
                    format_bool(dom.get('cp_is_active') or _('No info')),
                    format_bool(dom.get('internal', {}).get('commtrack_domain')),
                    dom.get('cp_n_out_sms', _("Not yet calculated")),
                    dom.get('cp_n_in_sms', _("Not yet calculated")),
                    dom.get('cp_n_sms_ever', _("Not yet calculated")),
                    dom.get('cp_n_sms_in_30_d', _("Not yet calculated")),
                    dom.get('cp_n_sms_out_30_d', _("Not yet calculated")),
                    format_bool(dom.get('internal', {}).get('custom_eula')),
                    dom.get('hipaa_compliant', _('false')),
                    dom.get('cp_j2me_90_d_bool', _('Not yet calculated')),
                ]


class AdminUserReport(AdminFacetedReport):
    slug = "user_list"
    name = ugettext_noop('User List')
    facet_title = ugettext_noop("User Facets")
    search_for = ugettext_noop("users...")
    default_sort = {'username.exact': 'asc'}
    es_index = 'users'

    es_facet_list = [
        "is_active",  # a user can log in to the project
        "is_staff",
        "is_superuser",
        "domain",
        "doc_type",
    ]

    es_facet_mapping = [
        ("", True, [
            {"facet": "is_active", "name": "Can Log In?", "expanded": True},
            {"facet": "is_superuser", "name": "SuperUser?", "expanded": True},
            {"facet": "is_staff", "name": "Staff?", "expanded": True},
            {"facet": "domain", "name": "Domain", "expanded": True},
            {"facet": "doc_type", "name": "User Type", "expanded": True},
        ]),
    ]

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Username"), prop_name="username.exact"),
            DataTablesColumn(_("Project Spaces")),
            DataTablesColumn(_("Date Joined"), prop_name="date_joined"),
            DataTablesColumn(_("Last Login"), prop_name="last_login"),
            DataTablesColumn(_("Type"), prop_name="doc_type"),
            DataTablesColumn(_("SuperUser?"), prop_name="is_superuser"),
        )
        return headers

    @property
    def export_rows(self):
        query = UserES().remove_default_filters()
        for u in query.scroll():
            yield self._format_row(u)

    @property
    def rows(self):
        users = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]
        for u in users:
            yield self._format_row(u)

    def _format_row(self, user):
        user_lookup_url = reverse('web_user_lookup')
        return [
            '<a href="%(url)s?q=%(username)s">%(username)s</a>' % {
                'url': user_lookup_url, 'username': user.get('username')
            },
            self._get_domains(user),
            self._format_date(user.get('date_joined'), _('No date')),
            self._format_date(user.get('last_login'), _('No date')),
            user.get('doc_type'),
            user.get('is_superuser'),
        ]

    def _format_date(self, dstr, default):
        # use [:19] so that only only the 'YYYY-MM-DDTHH:MM:SS' part of the string is parsed
        return datetime.strptime(dstr[:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y/%m/%d %H:%M:%S') if dstr else default

    def _get_domains(self, user):
        if user.get('doc_type') == "WebUser":
                return ", ".join([dm['domain'] for dm in user.get('domain_memberships', [])])
        return user.get('domain_membership', {}).get('domain', _('No Domain Data'))


def create_mapping_from_list(l, name="", expand_outer=False, expand_inner=False, name_change_fn=None):
    name_change_fn = name_change_fn or (lambda x: x)
    facets = [{"facet": item, "name": name_change_fn(item), "expanded": expand_inner} for item in sorted(l)]
    return (name, expand_outer, facets)


class AdminAppReport(AdminFacetedReport):
    slug = "app_list"
    name = ugettext_noop('Application List')
    facet_title = ugettext_noop("App Facets")
    search_for = ugettext_noop("apps...")
    default_sort = {'name.exact': 'asc'}
    es_index = 'apps'
    es_search_fields = ["name", "description", "domain", "_id", "copy_of", "comment", "build_comment"]

    excluded_properties = ["_id", "_rev", "_attachments", "external_blobs",
                           "admin_password_charset", "short_odk_url", "version",
                           "admin_password", "built_on", ]

    @property
    @memoized
    def profile_list(self):
        return [
            "profile.%s.%s" % (c['type'], c['id'])
            for c in get_custom_commcare_settings() if c['type'] != 'hq'
        ]
    calculated_properties_mapping = ("Calculations", True,
                                     [{"facet": "cp_is_active", "name": "Active", "expanded": True}])

    @property
    def properties(self):
        return [p for p in Application.properties().keys() if p and p not in self.excluded_properties]

    @property
    def es_facet_list(self):
        props = self.properties + self.profile_list + ["cp_is_active"]
        return [p for p in props if p not in self.excluded_properties]

    @property
    def es_facet_mapping(self):
        def remove_profile(name):
            return name[len("profile."):]
        profile_mapping = create_mapping_from_list(self.profile_list, "Profile", True, True, remove_profile)
        other_mapping = create_mapping_from_list(self.properties, "Other")
        return [profile_mapping, self.calculated_properties_mapping, other_mapping]

    @property
    def headers(self):
        headers = DataTablesHeader(
            DataTablesColumn(_("Name"), prop_name="name.exact"),
            DataTablesColumn(_("Project Space"), prop_name="domain"),
            DataTablesColumn(_("Build Comment"), prop_name="build_comment"),
        )
        return headers

    @property
    def rows(self):
        apps = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        for app in apps:
            yield [
                app.get('name'),
                app.get('domain'),
                app.get('build_comment'),
            ]


class GlobalAdminReports(AdminDomainStatsReport):
    base_template = "hqadmin/indicator_report.html"

    @property
    def template_context(self):
        context = super(GlobalAdminReports, self).template_context
        indicator_data = copy.deepcopy(INDICATOR_DATA)
        from django.urls import reverse
        for key in self.indicators:
            indicator_data[key]["ajax_url"] = reverse(
                indicator_data[key]["ajax_view"]
            )
            if not ("get_request_params" in indicator_data[key]):
                indicator_data[key]["get_request_params"] = {}
            indicator_data[key]["get_request_params"] = json.dumps(
                indicator_data[key]["get_request_params"]
            )
            if not ("interval" in indicator_data[key]):
                indicator_data[key]["interval"] = "month"
        context.update({
            'indicator_data': indicator_data,
            'indicators': self.indicators,
            'report_breadcrumbs': '<a href=".">%s</a>' % self.name,
        })
        return context

    @property
    def indicators(self):
        raise NotImplementedError


class RealProjectSpacesReport(GlobalAdminReports):
    slug = 'real_project_spaces'
    name = ugettext_noop('All Project Spaces')
    default_params = {'es_is_test': 'false'}
    indicators = [
        'domain_count',
        'domain_self_started_count',
        'active_domain_count',
        'active_community_domain_count',
        'active_self_started_domain_count',
        'countries',
        'active_countries',
        'active_cases',
        'users',
        'users_mobile',
        'users_web',
        'active_users_mobile',
        'forms',
        'forms_mobile',
        'forms_web',
        'forms_j2me',
        'subscriptions',
    ]


class CommConnectProjectSpacesReport(GlobalAdminReports):
    slug = 'commconnect_project_spaces'
    name = ugettext_noop('Project Spaces Using Messaging')
    default_params = {
        'es_is_test': 'false',
        'es_cp_sms_ever': 'T',
    }
    indicators = [
        'commconnect_domain_count',
        'sms_domain_count',
        'sms_only_domain_count',
        'incoming_sms_domain_count',
        'active_commconnect_domain_count',
        'active_dimagi_owned_gateways',
        'total_outgoing_sms',
        'total_incoming_sms',
        'total_outgoing_client_sms',
        'total_incoming_client_sms',
        'total_mobile_workers',
        'active_mobile_workers',
        'total_clients',
        'active_clients',
    ]


class CommTrackProjectSpacesReport(GlobalAdminReports):
    slug = 'commtrack_project_spaces'
    name = ugettext_noop('CommCare Supply Project Spaces')
    default_params = {
        'es_is_test': 'false',
        'es_internal.commtrack_domain': 'T',
    }
    indicators = [
        'commtrack_domain_count',
        'active_domain_count',
        'active_domain_count_forms',
        'active_domain_count_sms',
        'commtrack_total_outgoing_sms',
        'commtrack_total_incoming_sms',
        'commtrack_forms',
        'users_mobile',
        'active_users_mobile',
        'commtrack_users_web',
        'active_supply_points',
        'total_products',
        'stock_transactions',
        'unique_locations',
        'location_types',
    ]


class DeviceLogSoftAssertReport(BaseDeviceLogReport, AdminReport):
    base_template = 'reports/base_template.html'

    slug = 'device_log_soft_asserts'
    name = ugettext_lazy("Global Device Logs Soft Asserts")

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.devicelog.DeviceLogDomainFilter',
        'corehq.apps.reports.filters.devicelog.DeviceLogCommCareVersionFilter',
    ]
    emailable = False
    default_rows = 10

    _username_fmt = "%(username)s"
    _device_users_fmt = "%(username)s"
    _device_id_fmt = "%(device)s"
    _log_tag_fmt = "<label class='%(classes)s'>%(text)s</label>"

    @property
    def selected_domain(self):
        selected_domain = self.request.GET.get('domain', None)
        return selected_domain if selected_domain != '' else None

    @property
    def selected_commcare_version(self):
        commcare_version = self.request.GET.get('commcare_version', None)
        return commcare_version if commcare_version != '' else None

    @property
    def headers(self):
        headers = super(DeviceLogSoftAssertReport, self).headers
        headers.add_column(DataTablesColumn("Domain"))
        return headers

    @property
    def rows(self):
        logs = self._filter_logs()
        rows = self._create_rows(
            logs,
            range=slice(self.pagination.start, self.pagination.start + self.pagination.count)
        )
        return rows

    def _filter_logs(self):
        logs = DeviceReportEntry.objects.filter(
            date__range=[self.datespan.startdate_param_utc, self.datespan.enddate_param_utc]
        ).filter(type='soft-assert')

        if self.selected_domain is not None:
            logs = logs.filter(domain__exact=self.selected_domain)

        if self.selected_commcare_version is not None:
            logs = logs.filter(app_version__contains='"{}"'.format(self.selected_commcare_version))

        return logs

    def _create_row(self, log, *args, **kwargs):
        row = super(DeviceLogSoftAssertReport, self)._create_row(log, *args, **kwargs)
        row.append(log.domain)
        return row


class CommCareVersionReport(AdminFacetedReport):
    slug = "commcare_version"
    name = ugettext_lazy("CommCare Version")
    es_facet_list = DOMAIN_FACETS
    es_facet_mapping = FACET_MAPPING
    facet_title = ugettext_noop("Project Facets")

    @property
    def headers(self):
        versions = get_all_versions()
        headers = DataTablesHeader(
            DataTablesColumn(_("Project"))
        )
        for version in versions:
            headers.add_column(DataTablesColumn(version))
        return headers

    def es_query(self, params=None, size=None):
        size = size if size is not None else self.pagination.count
        return es_domain_query(params, self.es_facet_list, sort=self.get_sorting_block(),
                               start_at=self.pagination.start, size=size, fields=['name'])

    @property
    def rows(self):
        versions = get_all_versions()
        now = datetime.utcnow()
        days = now - timedelta(days=90)

        def get_data(domains):
            terms = [
                AggregationTerm('domain', 'domain'),
                AggregationTerm('commcare_version', 'form.meta.commcare_version')
            ]
            query = FormES().submitted(gte=days, lte=now).domain(domains).size(0)
            return NestedTermAggregationsHelper(base_query=query, terms=terms).get_data()
        rows = {}
        for domain in self.es_results.get('hits', {}).get('hits', []):
            domain_name = domain['fields']['name']
            rows.update({domain_name: [domain_name] + [0] * len(versions)})

        for data in get_data(list(rows.keys())):
            row = rows.get(data.domain, None)
            if row and data.commcare_version in versions:
                version_index = versions.index(data.commcare_version)
                row[version_index + 1] = data.doc_count

        return list(rows.values())


class AdminPhoneNumberReport(PhoneNumberReport):
    name = ugettext_lazy("Admin Phone Number Report")
    slug = 'phone_number_report'
    fields = [
        RequiredPhoneNumberFilter,
    ]

    dispatcher = AdminReportDispatcher
    default_report_url = '#'
    is_admin_report = True

    @property
    def shared_pagination_GET_params(self):
        return [
            {
                'name': RequiredPhoneNumberFilter.slug,
                'value': RequiredPhoneNumberFilter.get_value(self.request, domain=None)
            },
        ]

    @property
    @memoized
    def phone_number_filter(self):
        value = RequiredPhoneNumberFilter.get_value(self.request, domain=None)
        if isinstance(value, six.string_types):
            soft_assert_type_text(value)
            return apply_leniency(value.strip())

        return None

    def _get_queryset(self):
        return PhoneNumber.objects.filter(phone_number__contains=self.phone_number_filter)

    def _get_rows(self, paginate=True, link_user=True):
        owner_cache = {}
        if self.phone_number_filter:
            data = self._get_queryset()
        else:
            return

        if paginate and self.pagination:
            data = data[self.pagination.start:self.pagination.start + self.pagination.count]

        for number in data:
            yield self._fmt_row(number, owner_cache, link_user)

    @property
    def total_records(self):
        return self._get_queryset().count()


class UserAuditReport(AdminReport, DatespanMixin):
    base_template = 'reports/base_template.html'

    slug = 'user_audit_report'
    name = ugettext_lazy("User Audit Events")

    fields = [
        'corehq.apps.reports.filters.dates.DatespanFilter',
        'corehq.apps.reports.filters.simple.SimpleUsername',
        'corehq.apps.reports.filters.simple.SimpleDomain',
    ]
    emailable = False
    exportable = True
    default_rows = 10

    @property
    def selected_domain(self):
        selected_domain = self.request.GET.get('domain_name', None)
        return selected_domain if selected_domain != '' else None

    @property
    def selected_user(self):
        return self.request.GET.get('username', None)

    @property
    def headers(self):
        return DataTablesHeader(
            DataTablesColumn(ugettext_lazy("Date")),
            DataTablesColumn(ugettext_lazy("Username")),
            DataTablesColumn(ugettext_lazy("Domain")),
            DataTablesColumn(ugettext_lazy("IP Address")),
            DataTablesColumn(ugettext_lazy("Request Path")),
        )

    @property
    def rows(self):
        rows = []
        event_ids = navigation_event_ids_by_user(
            self.selected_user, self.datespan.startdate, self.datespan.enddate
        )
        for event_doc in iter_docs(NavigationEventAudit.get_db(), event_ids):
            event = NavigationEventAudit.wrap(event_doc)
            if not self.selected_domain or self.selected_domain == event.domain:
                rows.append([
                    event.event_date, event.user, event.domain or '', event.ip_address, event.request_path
                ])
        return rows
