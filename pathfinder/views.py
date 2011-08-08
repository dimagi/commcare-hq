from datetime import datetime, date
from dimagi.utils.couch.database import get_db
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.queryable_set import QueryableList
import string
from django.http import Http404
from django.shortcuts import render_to_response
from django.template.context import RequestContext
import functools

class PathfinderPatientGroup(QueryableList):
    def __init__(self):

        self._new = lambda x: x['registered_this_month']
        self._followup = lambda x: x['followup_this_month']

        self._f = lambda x: x['followup_this_month'] and (x['registration_and_followup_hiv'] == 'continuing' or x['registration_and_followup_hiv'] == '')


        self._0to14 = lambda x: 0 <= x['age'] <= 14
        self._15to24 = lambda x: 15 <= x['age'] <= 24
        self._25to49 = lambda x: 25 <= x['age'] <= 49
        self._50plus = lambda x: 50 <= x['age']
        self._child = lambda x: 18 < x['age']
        self._adult = lambda x: 18 >= x['age']

        self._hiv_reg = lambda x: x['registration_cause'].count('hiv')

        self._hiv_unk = lambda x: (x['hiv_status_during_registration'] is None or \
                                    (x['hiv_status_during_registration'].lower() != 'positive' and \
                                    x['hiv_status_during_registration'].lower() != 'negative')) \
                                    and \
                                    (x['hiv_status_after_test'].lower() is None or \
                                    (x['hiv_status_after_test'].lower() != 'positive' and \
                                    x['hiv_status_after_test'].lower() != 'negative'))
        self._hiv_pos = lambda x: (x['hiv_status_during_registration'].lower() == 'positive' or  x['hiv_status_after_test'].lower() == 'positive')
        self._hiv_neg = lambda x: x['hiv_status_during_registration'].lower() != 'positive' and  x['hiv_status_after_test'].lower() == 'negative'


        self._ctc_arv = lambda x: x['ctc'].count('and_arvs') > 0
        self._ctc_no_arv = lambda x: x['ctc'].count('no_arvs') > 0
        self._ctc_no_reg = lambda x: x['ctc'] == "not_registered"

        self._male = lambda x: x['sex'] == 'm'
        self._female = lambda x: x['sex'] == 'f'

        self._continuing = lambda x: x['registration_and_followup_hiv'] == 'continuing'

        self._deaths = lambda x: x['registration_and_followup_hiv'] == 'dead'
        self._losses = lambda x: x['registration_and_followup_hiv'] == 'lost'
        self._migrations = lambda x: x['registration_and_followup_hiv'] == 'migrated'
        self._transfers = lambda x: x['registration_and_followup_hiv'] == 'transferred'
        self._no_need = lambda x: x['registration_and_followup_hiv'] == 'no_need'
        self._opted_out = lambda x: x['registration_and_followup_hiv'] == 'opted_out'

        self._vct = lambda x: x['referrals_hiv'].count('counselling_and_testing') > 0
        self._ois = lambda x: x['referrals_hiv'].count('opportunistic_infections') > 0
        self._ctc = lambda x: x['referrals_hiv'].count('referred_to_ctc') > 0
        self._pmtct = lambda x: x['referrals_hiv'].count('prevention_from_mother_to_child') > 0
        self._fp = lambda x: x['referrals_hiv'].count('ref_fp') > 0
        self._sg = lambda x: x['referrals_hiv'].count('other_services') > 0
        self._tb = lambda x: x['referrals_hiv'].count('tb_clinic') > 0

def retrieve_providers(domain, ward):
    results = get_db().view('pathfinder/pathfinder_gov_chw', keys=[[domain, ward]], include_docs=True).all()
    chws = QueryableList()
    for result in results:
        p = dict()
#        (p['login_id'] , p['region'] , p['district'] , p['name'] , p['id'] , p['sex'] , p['training'] ,
#         p['trainingorg'] , p['trainingdays'] , p['user_type'] , p['supervisorname'] ,
#         p['supervisorfacility'] , p['supervisorid'] , p['orgsupervisor'] ) = result['value']
        p['reported_this_month'] = False

        p.update(result['doc']['commcare_accounts'][0]['user_data'])
        #result['doc']
        chws += [p]
    return chws

def get_provider_info(domain, provider):
    results = get_db().view('pathfinder/pathfinder_gov_chw_by_name', keys=[[domain, provider]], include_docs=True).all()
    if len(results) < 1:
        raise Http404("Couldn't find that provider.")
    return results[0]['doc']['commcare_accounts'][0]['user_data']

def get_patients_by_provider(domain, provider):
    return get_db().view('pathfinder/pathfinder_gov_reg_by_username', keys=[[domain, provider]], include_docs=True).all()
 
def retrieve_patient_group(user_ids, domain, year, month):
    caseid_set = set()
    patients = {}
    year = int(year)
    month = int(month)
    for result in user_ids:
        rform = result['doc']['form'] #shortcut
        regdate = datetime.strptime(rform['patient']['date_of_registration'], '%Y-%m-%d')
        pyear, pmonth = regdate.year, regdate.month
        if pyear > year or (pyear == year and pmonth > month): # Exclude patients newer than this report.
            continue
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
#                  'type_of_client',
                  'referrals_hiv',
                  'ctc',
#                  'followup_this_month',
                  'medication_given',
                  'services',
                  'referrals']:
            p[i] = ''
        patients[p['case_id'] ] = p
    update_patients_with_followups(domain, patients, caseid_set,year,month)
    update_patients_with_referrals(patients,caseid_set,year,month)
    #map(lambda x: patients.__delitem__(x), filter(lambda y: not patients[y]['followup_this_month'], patients.keys()))
    gp =  PathfinderPatientGroup()
    gp += patients.values()
    return gp

def update_patients_with_followups(domain, patients, caseid_set, year, month):
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

def ward_summary(request, domain, ward, year, month, template="pathfinder-reports/ward_summary.html"):
    # First, get all the registrations for the given ward.
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg', keys=[[domain, ward]], include_docs=True).all()

    provs = retrieve_providers(domain, ward)
    prov_p = {}
    refs_p = {}
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

def provider_summary(request, domain, name, year,month, template="pathfinder-reports/provider_summary.html"):
#    user_ids = get_db().view('pathfinder/pathfinder_gov_reg_by_username', keys=[[domain, username]]).all()
#    return retrieve_patient_group(user_ids, domain, year, month)
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

def update_patients_with_referrals(patients, ids, year,month):
    refs = get_db().view('pathfinder/pathfinder_gov_referral', keys=[[x] for x in list(ids)], include_docs=True).all()
    for p in patients: patients[p]['referrals_completed'] = 0
    for r in refs:
        d = datetime.strptime(r['doc']['form']['meta']['timeEnd'], "%Y-%m-%dT%H:%M:%SZ")
        if d.month == month and d.year == year and r['doc']['form']['client']['referral'] == 'yes':
            patients[r['doc']['form']['case']['case_id']]['referrals_completed'] += 1

def hbc_selector(request, domain, template="pathfinder-reports/select_hbc_summary.html"):
    pass

#@login_and_domain_required
def home_based_care(request, domain, ward, year, month, template="pathfinder-reports/hbc.html"):
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