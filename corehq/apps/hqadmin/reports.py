import copy
from datetime import datetime
import json
from dimagi.utils.decorators.memoized import memoized
from corehq import Domain
from corehq.apps.accounting.models import (
    SoftwarePlanEdition,
    Subscription,
)
from corehq.apps.app_manager.models import Application
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn
from corehq.apps.reports.dispatcher import AdminReportDispatcher
from corehq.apps.reports.generic import ElasticTabularReport, GenericTabularReport
from corehq.apps.reports.standard.domains import DomainStatsReport, es_domain_query
from django.utils.translation import ugettext as _, ugettext_noop
from corehq.apps.users.models import WebUser
from corehq.elastic import es_query, parse_args_for_es, fill_mapping_with_facets
from corehq.pillows.mappings.app_mapping import APP_INDEX
from corehq.pillows.mappings.user_mapping import USER_INDEX
from corehq.apps.app_manager.commcare_settings import get_custom_commcare_settings
from corehq.toggles import IS_DEVELOPER
from corehq.apps.reports.datatables import DataTablesHeader, DataTablesColumn, DTSortType
from django.utils.safestring import mark_safe
from django.core.urlresolvers import reverse


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
        "xaxis_label": "# workers",
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
        "chart_name": "active_cases",
        "chart_title": "Active Supply Points (last 90 days)",
        "hide_cumulative_charts": True,
        "get_request_params": {
            "supply_points": True
        },
        "histogram_type": "active_cases",
        "is_cumulative": False,
        "xaxis_label": "# cases",
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
    "deployment.date",
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
    "internal.services",
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
    "is_public",
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
    "tags",
]

FACET_MAPPING = [
    ("Activity", True, [
        {"facet": "is_test", "name": "Test Project", "expanded": True},
        {"facet": "cp_is_active", "name": "Active", "expanded": True},
        # {"facet": "deployment.date", "name": "Deployment Date", "expanded": False},
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
    ]),
    ("Plans", False, [
        {"facet": "project_type", "name": "Project Type", "expanded": False},
        {"facet": "customer_type", "name": "Customer Type", "expanded": False},
        {"facet": "internal.initiative.exact", "name": "Initiative", "expanded": False},
        {"facet": "internal.services", "name": "Services", "expanded": False},
        {"facet": "is_sms_billable", "name": "SMS Billable", "expanded": False},
    ]),
    ("Eula", False, [
        {"facet": "internal.can_use_data", "name": "Public Data", "expanded": True},
        {"facet": "custom_eula", "name": "Custom Eula", "expanded": False},
    ]),
]


class AdminReport(GenericTabularReport):
    dispatcher = AdminReportDispatcher
    base_template = "hqadmin/faceted_report.html"


class AdminFacetedReport(AdminReport, ElasticTabularReport):
    default_sort = None
    es_prefix = "es_"  # facet keywords in the url will be prefixed with this
    asynchronous = False
    ajax_pagination = True
    exportable = True
    es_queried = False
    es_facet_list = []
    es_facet_mapping = []
    section_name = ugettext_noop("ADMINREPORT")
    es_url = ''

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
        for param in self.request.GET.iterlists():
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
                        "match": {
                            "_all": {
                                "query": search_query,
                                "operator": "and", }}}}}

        q["facets"] = {}

        q["sort"] = self.get_sorting_block()
        start_at = self.pagination.start
        size = size if size is not None else self.pagination.count
        return es_query(params, self.es_facet_list, terms, q, self.es_url, start_at, size, facet_size=25)

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

    @property
    def template_context(self):
        ctxt = super(AdminDomainStatsReport, self).template_context
        ctxt["interval"] = "week"

        ctxt["domain_datefields"] = [
            {"value": "date_created", "name": _("Date Created")},
            {"value": "deployment.date", "name": _("Deployment Date")},
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
            DataTablesColumn(_("Deployment Date"), prop_name="deployment.date"),
            DataTablesColumn(_("Deployment Country"), prop_name="deployment.countries.exact"),
            DataTablesColumn(_("# Active Mobile Workers"), sort_type=DTSortType.NUMERIC,
                prop_name="cp_n_active_cc_users",
                help_text=_("the number of mobile workers who have submitted a form or sent or received an SMS "
                            "in the last 30 days.  Includes deactivated workers.")),
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
            DataTablesColumn(_("First Form Submission"), prop_name="cp_first_form"),
            DataTablesColumn(_("Last Form Submission"), prop_name="cp_last_form"),
            DataTablesColumn(_("# Web Users"), sort_type=DTSortType.NUMERIC,
                             prop_name="cp_n_web_users",
                             help_text=_("Does not include deactivated users.")),
            DataTablesColumn(_("Notes"), prop_name="internal.notes"),
            DataTablesColumn(_("Services"), prop_name="internal.services"),
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
        )
        return headers

    @property
    def rows(self):
        domains = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        def get_from_stat_facets(prop, what_to_get):
            return self.es_results.get('facets', {}).get('%s-STATS' % prop, {}).get(what_to_get)

        CALCS_ROW_INDEX = {
            5: "cp_n_active_cc_users",
            6: "cp_n_cc_users",
            7: "cp_n_users_submitted_form",
            8: "cp_n_60_day_cases",
            9: "cp_n_active_cases",
            10: "cp_n_inactive_cases",
            11: "cp_n_cases",
            12: "cp_n_forms",
            15: "cp_n_web_users",
            28: "cp_n_out_sms",
            29: "cp_n_in_sms",
            30: "cp_n_sms_ever",
            31: "cp_n_sms_in_30_d",
            32: "cp_n_sms_out_30_d",
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
                return u"{}".format(val)
            return _('No info')

        for dom in domains:
            if dom.has_key('name'):  # for some reason when using the statistical facet, ES adds an empty dict to hits
                yield [
                    self.get_name_or_link(dom, internal_settings=True),
                    format_date((dom.get("date_created")), _('No date')),
                    dom.get("internal", {}).get('organization_name') or _('No org'),
                    format_date((dom.get('deployment') or {}).get('date'), _('No date')),
                    (dom.get("deployment") or {}).get('countries') or _('No countries'),
                    dom.get("cp_n_active_cc_users", _("Not yet calculated")),
                    dom.get("cp_n_cc_users", _("Not yet calculated")),
                    dom.get("cp_n_users_submitted_form", _("Not yet calculated")),
                    dom.get("cp_n_60_day_cases", _("Not yet calculated")),
                    dom.get("cp_n_active_cases", _("Not yet calculated")),
                    dom.get("cp_n_inactive_cases", _("Not yet calculated")),
                    dom.get("cp_n_cases", _("Not yet calculated")),
                    dom.get("cp_n_forms", _("Not yet calculated")),
                    format_date(dom.get("cp_first_form"), _("No forms")),
                    format_date(dom.get("cp_last_form"), _("No forms")),
                    dom.get("cp_n_web_users", _("Not yet calculated")),
                    dom.get('internal', {}).get('notes') or _('No notes'),
                    dom.get('internal', {}).get('services') or _('No info'),
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
                ]


class AdminUserReport(AdminFacetedReport):
    slug = "user_list"
    name = ugettext_noop('User List')
    facet_title = ugettext_noop("User Facets")
    search_for = ugettext_noop("users...")
    default_sort = {'username.exact': 'asc'}
    es_url = USER_INDEX + '/user/_search'

    es_facet_list = [
        "is_active",  # this is NOT "has submitted a form in the last 30 days"
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
    def rows(self):
        users = [res['_source'] for res in self.es_results.get('hits', {}).get('hits', [])]

        def format_date(dstr, default):
            # use [:19] so that only only the 'YYYY-MM-DDTHH:MM:SS' part of the string is parsed
            return datetime.strptime(dstr[:19], '%Y-%m-%dT%H:%M:%S').strftime('%Y/%m/%d %H:%M:%S') if dstr else default

        def get_domains(user):
            if user.get('doc_type') == "WebUser":
                return ", ".join([dm['domain'] for dm in user.get('domain_memberships', [])])
            return user.get('domain_membership', {}).get('domain', _('No Domain Data'))

        for u in users:
            yield [
                u.get('username'),
                get_domains(u),
                format_date(u.get('date_joined'), _('No date')),
                format_date(u.get('last_login'), _('No date')),
                u.get('doc_type'),
                u.get('is_superuser'),
            ]


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
    es_url = APP_INDEX + '/app/_search'

    excluded_properties = ["_id", "_rev", "_attachments", "admin_password_charset", "short_odk_url", "version",
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
        return filter(lambda p: p and p not in self.excluded_properties, Application.properties().keys())

    @property
    def es_facet_list(self):
        props = self.properties + self.profile_list + ["cp_is_active"]
        return filter(lambda p: p not in self.excluded_properties, props)

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
    section_name = ugettext_noop("ADMINREPORT")  # not sure why ...

    @property
    def template_context(self):
        context = super(GlobalAdminReports, self).template_context
        indicator_data = copy.deepcopy(INDICATOR_DATA)
        from django.core.urlresolvers import reverse
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
