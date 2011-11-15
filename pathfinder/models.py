from corehq.apps.reports.custom import HQReport, ReportField
from datetime import date
from pathfinder.views import retrieve_patient_group, retrieve_providers, get_provider_info, get_patients_by_provider
from django.http import Http404
from dimagi.utils.couch.database import get_db

class PathfinderWardSummaryReport(HQReport):
    name = "Ward Summary"
    slug = "ward"
    template_name = "pathfinder-reports/ward_summary.html"
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'pathfinder.models.WardSelect']

    def calc(self):
        ward = self.request.GET.get("ward", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (ward and month and year):
            return #raise Http404("Ward, month, or year not set.")

        provs = retrieve_providers(self.domain, ward)
        prov_p = {} # Providers, indexed by name.
        refs_p = {} # Referrals, indexed by name.
        for p in provs:
            x = retrieve_patient_group(get_patients_by_provider(self.domain, p['full_name']), self.domain, year, month)
            prov_p[p['full_name']] = x
            refs_p[p['full_name']] = sum([a['referrals_completed'] for a in x])
        self.context['ward'] = ward
        self.context['year'] = year
        self.context['month'] = month
        self.context['provs'] = provs
        self.context['prov_p'] = prov_p
        self.context['refs_p'] = refs_p

class PathfinderProviderReport(HQReport):
    name = "Provider"
    slug = "provider"
    template_name = "pathfinder-reports/provider_summary.html"
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'pathfinder.models.ProviderSelect']


    def calc(self):
        name = self.request.GET.get("name", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (name and month and year):
            return #raise Http404("Ward, month, or year not set.")


        self.context['p'] = get_provider_info(self.domain, name)
        self.context['name'] = name
        pre = get_patients_by_provider(self.domain, name)
        patients = {}
        for p in pre:
            pd = dict()
            pd.update(p['doc']['form']['patient'])
            pd['case_id'] = p['doc']['form']['case']['case_id']

            patients[pd['case_id']] = pd
        g = retrieve_patient_group(pre, self.domain, year,month)
        self.context['year'] = year
        self.context['month'] = month
        self.context['patients'] = g

class PathfinderHBCReport(HQReport):
    name = "Home-Based Care"
    slug = "hbc"
    template_name = "pathfinder-reports/hbc.html"
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'pathfinder.models.WardSelect']

    def calc(self):
        ward = self.request.GET.get("ward", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (ward and month and year):
            return #raise Http404("Ward, month, or year not set.")

        user_ids = get_db().view('pathfinder/pathfinder_gov_reg', keys=[[self.domain, ward]], include_docs=True).all()
        print user_ids
        self.context['p'] = retrieve_patient_group(user_ids, self.domain, year, month)
        chws = retrieve_providers(self.domain, ward)
        chws._reported = lambda x: x['reported_this_month']
        for c in chws:
            if len(filter(lambda x: x['provider'] == c['full_name'], self.context['p'].followup)):
                c['reported_this_month'] = True
            else:
                c['reported_this_month'] = False
        self.context['chws'] = chws
        self.context['ward'] = ward
        self.context['date'] = date(year=int(year),month=int(month), day=01)

class ProviderSelect(ReportField):
    slug = "provider"
    template = "pathfinder-reports/provider-select.html"

    def update_context(self):
        results = get_db().view('pathfinder/pathfinder_gov_chw_by_name').all()
        self.context['names'] = [result['key'][1] for result in results]
        self.context['provider'] = self.request.GET.get('provider', None)


class WardSelect(ReportField):
    slug = "ward"
    template = "pathfinder-reports/ward-select.html"

    def update_context(self):
        results = get_db().view('pathfinder/pathfinder_all_wards', group=True).all()
        res = [result['key'] for result in results]
        self.context['wards'] = [{"district": result[1], "ward": result[2]} for result in res]
        self.context['ward'] = self.request.GET.get('ward', None)
