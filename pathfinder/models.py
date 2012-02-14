from couchdbkit.ext.django.schema import Document
from corehq.apps.reports.custom import HQReport, ReportField
from datetime import date
from pathfinder.views import retrieve_patient_group, get_patients_by_provider
from django.http import Http404
from dimagi.utils.couch.database import get_db
from corehq.apps.groups.models import Group

from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from dimagi.utils.queryable_set import QueryableList
from couchforms.models import XFormInstance

class _(Document): pass

class PathfinderWardSummaryReport(HQReport):
    name = "Ward Summary"
    slug = "ward"
    template_name = "pathfinder-reports/ward_summary.html"
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'corehq.apps.reports.fields.GroupField']

    def calc(self):
        ward = self.request.GET.get("group", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (ward and month and year):
            return #raise Http404("Ward, month, or year not set.")
        ward = Group.get(ward)
        #provs = retrieve_providers(self.domain, ward)
        provs = map(CommCareUser.get, ward.users)
        prov_p = {} # Providers, indexed by name.
        refs_p = {} # Referrals, indexed by name.
        for p in provs:
            x = retrieve_patient_group(get_patients_by_provider(self.domain, p._id), self.domain, year, month)
            prov_p[p.get_id] = x
            refs_p[p.get_id] = sum([a['referrals_completed'] for a in x])
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
        name = self.request.GET.get("user", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (name and month and year):
            return #raise Http404("Ward, month, or year not set.")


        self.context['p'] = CommCareUser.get(name)#get_provider_info(self.domain, name)
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
    fields = ['corehq.apps.reports.custom.MonthField', 'corehq.apps.reports.custom.YearField', 'corehq.apps.reports.fields.GroupField']
    def calc(self):
        ward = self.request.GET.get("group", None)
        month = self.request.GET.get("month", None)
        year = self.request.GET.get("year", None)
        if not (ward and month and year):
            return #raise Http404("Ward, month, or year not set.")

        ward = Group.get(ward)

        user_ids = get_db().view('pathfinder/pathfinder_gov_reg_by_username', keys=[[self.domain, w] for w in ward.users], include_docs=True).all()
        self.context['p'] = retrieve_patient_group(user_ids, self.domain, year, month)
        chws = QueryableList(map(CommCareUser.get, ward.users))
        chws._reported = lambda x: x['reported_this_month']
        for c in chws:
            r = XFormInstance.view('pathfinder/pathfinder_xforms',
                key=['pathfinder', c.get_id, int(year), int(month)],
                reduce=True
            ).one()
            c['reported_this_month'] = (r != None)

        self.context['chws'] = chws
        self.context['ward'] = ward
        self.context['date'] = date(year=int(year),month=int(month), day=01)

class ProviderSelect(ReportField):
    slug = "provider"
    template = "pathfinder-reports/provider-select.html"

    def update_context(self):
        results = CommCareUser.by_domain('pathfinder')
        self.context['names'] = {}
        for result in results:
            self.context['names'].update({result.user_data['full_name']: result.get_id})
        self.context['provider'] = self.request.GET.get('user', None)
