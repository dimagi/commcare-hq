from datetime import datetime, date
from dimagi.utils.couch.database import get_db
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.queryable_set import QueryableList
from django.http import Http404
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from patient_group import PathfinderPatientGroup


def selector(request, domain, template="pathfinder-reports/select.html"):
    """
    Selector for all reports.
    """
    return render_to_response(template, {'domain': domain}, context_instance=RequestContext(request))


def ward_selector(request, domain, template="pathfinder-reports/select_ward_summary.html"):
    """
    Select parameters for ward summary report.
    """
    results = get_db().view('pathfinder/pathfinder_all_wards', group=True).all()
    res = [result['key'] for result in results]
    wards = [{"district": result[1], "ward": result[2]} for result in res]
    return render_to_response(template,
                             {"wards": wards,
                              "years": range(2008, datetime.now().year + 1), # less than ideal but works
                              "domain": domain,},
                             context_instance=RequestContext(request))

def hbc_selector(request, domain, template="pathfinder-reports/select_hbc_summary.html"):
    """
    Select parameters for HBC summary report.
    """
    results = get_db().view('pathfinder/pathfinder_all_wards', group=True).all()
    res = [result['key'] for result in results]
    wards = [{"district": result[1], "ward": result[2]} for result in res]
    return render_to_response(template,
                             {"wards": wards,
                              "years": range(2008, datetime.now().year + 1), # less than ideal but works
                              "domain": domain,},
                             context_instance=RequestContext(request))



def provider_selector(request, domain, template="pathfinder-reports/select_provider_summary.html"):
    """
    Select parameters for provider report.
    """
    results = get_db().view('pathfinder/pathfinder_gov_chw_by_name').all()
    names = [result['key'][1] for result in results]
    return render_to_response(template,
                             {"names": names,
                              "years": range(2008, datetime.now().year + 1), # less than ideal but works
                              "domain": domain,},
                             context_instance=RequestContext(request))


#@login_and_domain_required
def ward_summary(request, domain,  template="pathfinder-reports/ward_summary.html"):
    """
    Ward summary report.
    """
    ward = request.GET.get("ward", None)
    month = request.GET.get("month", None)
    year = request.GET.get("year", None)
    if not (ward and month and year):
        raise Http404
    provs = retrieve_providers(domain, ward)
    prov_p = {} # Providers, indexed by name.
    refs_p = {} # Referrals, indexed by name.
    for p in provs:
        x = retrieve_patient_group(get_patients_by_provider(domain, p['full_name']), domain, year, month)
        prov_p[p['full_name']] = x
        refs_p[p['full_name']] = sum([a['referrals_completed'] for a in x])
    context = RequestContext(request)
    context['ward'] = ward
    context['year'] = year
    context['month'] = month
    context['provs'] = provs
    context['prov_p'] = prov_p
    context['refs_p'] = refs_p
    context['domain'] = domain
    return render_to_response(template, context)

#@login_and_domain_required
def provider_summary(request, domain, template="pathfinder-reports/provider_summary.html"):
    """
    Provider summary report.
    """
    name = request.GET.get("name", None)
    month = request.GET.get("month", None)
    year = request.GET.get("year", None)
    if not (name and month and year):
        raise Http404

    context = RequestContext(request)
    context['p'] = get_provider_info(domain, name)
    pre = get_patients_by_provider(domain, name)
    patients = {}
    for p in pre:
        pd = dict()
        pd.update(p['doc']['form']['patient'])
        pd['case_id'] = p['doc']['form']['case']['case_id']

        patients[pd['case_id']] = pd
    g = retrieve_patient_group(pre, domain, year,month)
    context['year'] = year
    context['month'] = month
    context['patients'] = g
    return render_to_response(template,context)

#@login_and_domain_required
def home_based_care(request, domain, template="pathfinder-reports/hbc.html"):
    """
    Home-based care report.
    """
    ward = request.GET.get("ward", None)
    month = request.GET.get("month", None)
    year = request.GET.get("year", None)
    if not (ward and month and year):
        raise Http404

    context = RequestContext(request)
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg', keys=[[domain, ward]], include_docs=True).all()
    context['p'] = retrieve_patient_group(user_ids, domain, year, month)
    chws = retrieve_providers(domain, ward)
    chws._reported = lambda x: x['reported_this_month']
    for c in chws:
        if len(filter(lambda x: x['provider'] == c['full_name'], context['p'].followup)):
            c['reported_this_month'] = True
        else:
            c['reported_this_month'] = False
    context['chws'] = chws
    context['ward'] = ward
    context['domain'] = domain
    context['date'] = date(year=int(year),month=int(month), day=01)
    return render_to_response(template, context)

####################
# Utility functions

def retrieve_providers(domain, ward):
    """
    Given a domain and a ward, retrieve all providers matching that domain.
    """
    results = get_db().view('pathfinder/pathfinder_gov_chw', keys=[[domain, ward]], include_docs=True).all()
    providers = QueryableList()
    for result in results:
        p = dict()
        p['reported_this_month'] = False
        p.update(result['doc']['commcare_accounts'][0]['user_data'])
        providers += [p]
    return providers


def get_provider_info(domain, provider):
    results = get_db().view('pathfinder/pathfinder_gov_chw_by_name', keys=[[domain, provider]], include_docs=True).all()
    if len(results) < 1:
        raise Http404("Couldn't find that provider.")
    return results[0]['doc']['commcare_accounts'][0]['user_data']


def get_patients_by_provider(domain, provider):
    return get_db().view('pathfinder/pathfinder_gov_reg_by_username', keys=[[domain, provider]], include_docs=True).all()


def retrieve_patient_group(user_ids, domain, year, month):
    """
    Given a set of user IDs, retrieve all patients matching that set.  Update them with followup and referral form info.
    """
    caseid_set = set()
    patients = {}
    year = int(year)
    month = int(month)
    pyear = 0
    pmonth = 0
    for result in user_ids:
        rform = result['doc']['form'] #shortcut
        try: # strptime() can fail if the CHW enters weird data.
            regdate = datetime.strptime(rform['patient']['date_of_registration'], '%Y-%m-%d')

            pyear, pmonth = regdate.year, regdate.month
            if pyear > year or (pyear == year and pmonth > month): # Exclude patients newer than this report.
                continue
        except:
            pass
        p = dict()
        age_tmp = map(int, rform['patient']['date_of_birth'].split('-'))
        p['age'] = year - age_tmp[0] if age_tmp[1] < month else (year - age_tmp[0]) - 1
        p.update(rform['case'])
        p.update(rform['patient'])
        caseid_set.add(p['case_id'] )
        p['ward'] = p['village']
        p['registered_this_month'] = True if (pyear == year and pmonth + 1 == month) else False # months are 0-indexed
        p['followup_this_month'] = 0
        p['referrals_made'] = 0
        for i in ['provider',
                  'registration_and_followup_hiv',
                  'referrals_hiv',
                  'ctc',
                  'medication_given',
                  'services',
                  'referrals']:
            p[i] = ''
        patients[p['case_id'] ] = p
    update_patients_with_followups(domain, patients, caseid_set,year,month)
    update_patients_with_referrals(patients,caseid_set,year,month)
    ## I chose not to remove patients without followups this month -- sometimes there's a referral in a month with no followup.
    # map(lambda x: patients.__delitem__(x), filter(lambda y: not patients[y]['followup_this_month'], patients.keys()))
    gp =  PathfinderPatientGroup()
    gp += patients.values()
    return gp


def update_patients_with_followups(domain, patients, caseid_set, year, month):
    """
    Given a set of patients, update them with info from followup forms.
    """
    followup_keys = [[domain, x] for x in list(caseid_set)]
    followups = get_db().view('pathfinder/pathfinder_gov_followup_by_caseid', keys = followup_keys, include_docs=True).all()
    for f in followups:
        if not f['key'][1] in patients:
            continue
        p = patients[f['key'][1]]
        fyear, fmonth = f['value'][5], f['value'][6]
        p['followup_this_month'] = 0
        if fyear != year or fmonth != month:
            continue
        f = f['doc']['form']
        fp = f['patient']
        p['provider'] = f['meta']['username']

        # The code below exists to hack around issues like people coming back to life after being dead,
        # multiple followups in a single month having different services, medication, and/or referral values,
        # and so on.

        if not p.has_key('registration_and_followup_hiv') or p['registration_and_followup_hiv'] == 'continuing' or p['registration_and_followup_hiv'] == '': # don't allow a value of 'dead' to change
            p['registration_and_followup_hiv'] = fp['reg_followup_hiv']
        p['followup_this_month'] += 1 if (fyear == year and fmonth == month) else 0
        if "medication_given" in fp and fp['medication_given']:
            p['medication_given'] += fp['medication_given'] + " "
        if "services_given" in fp and fp['services_given']:
            p['services'] += fp['services_given'] + " "
        if "referrals_hiv" in fp and fp['referrals_hiv']:
            p['referrals'] += fp['referrals_hiv'] + " "
        p.update(fp)


def update_patients_with_referrals(patients, ids, year,month):
    """
    Given a set of patients, count how many completed referrals they had in that month.
    """
    refs = get_db().view('pathfinder/pathfinder_gov_referral', keys=[[x] for x in list(ids)], include_docs=True).all()
    for p in patients: patients[p]['referrals_completed'] = 0
    for r in refs:
        d = datetime.strptime(r['doc']['form']['meta']['timeEnd'], "%Y-%m-%dT%H:%M:%SZ")
        if d.month == month and d.year == year and r['doc']['form']['client']['referral'] == 'yes':
            patients[r['doc']['form']['case']['case_id']]['referrals_completed'] += 1

