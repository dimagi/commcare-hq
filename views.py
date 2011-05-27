from datetime import datetime, date
from dimagi.utils.couch.database import get_db
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.queryable_set import QueryableList
import string
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
        p = PathfinderProvider()
        (p['login_id'] , p['region'] , p['district'] , p['name'] , p['id'] , p['sex'] , p['training'] ,
         p['trainingorg'] , p['trainingdays'] , p['user_type'] , p['supervisorname'] ,
         p['supervisorfacility'] , p['supervisorid'] , p['orgsupervisor'] ) = result['value']
        chws.add(p)
    return chws

def retrieve_patient_group(user_ids, domain, year, month):
    caseid_set = set()
    patients = {}
    year = int(year)
    month = int(month)
    for result in user_ids:
        rform = result['doc']['form'] #shortcut
        pyear, pmonth = result['value'][1], result['value'][2]
        print pyear, pmonth, year, month
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
        p['followup_this_month'] = False
        for i in ['provider',
                  'registration_and_followup_hiv',
                  'type_of_client',
                  'referrals_hiv',
                  'ctc',
                  'followup_this_month',
                  'hiv_status_during_registration']:
            p[i] = ''
        patients[p['case_id'] ] = p
    followup_keys = [[domain, x] for x in list(caseid_set)]
    followups = get_db().view('pathfinder/pathfinder_gov_followup', keys = followup_keys).all()
    for f in followups:
        p = patients[f['key'][1]]
        p['provider'] = f['value'][0]
        if p['registration_and_followup_hiv'] == 'continuing' or p['registration_and_followup_hiv'] == '': # don't allow a value of 'dead' to change
            p['registration_and_followup_hiv'] = f['value'][1]
        p['type_of_client'] = f['value'][2]
        p['referrals_hiv'] = f['value'][3]
        p['ctc'] = f['value'][4]
        p['followup_this_month'] = True
    #map(lambda x: patients.__delitem__(x), filter(lambda y: patients[y]['followup_this_month'] == False, patients.keys()))
    gp =  PathfinderPatientGroup()
    gp += patients.values()
    return gp

def ward_summary(domain, ward, year, month):
    # First, get all the registrations for the given ward.
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg', keys=[[domain, ward]], include_docs=True).all()
    providers =
    return retrieve_patient_group(user_ids, domain, year, month)


def provider_summary(domain, username, year,month):
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg_by_username', keys=[[domain, username]]).all()
    return retrieve_patient_group(user_ids, domain, year, month)

#@login_and_domain_required
def home_based_care(request, domain, ward, year, month, template="pathfinder-reports/hbc.html"):
    context = RequestContext(request)
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg', keys=[[domain, ward]], include_docs=True).all()
    context['p'] = retrieve_patient_group(user_ids, domain, year, month)

    context['ward'] = ward
    context['date'] = date(year=int(year),month=int(month), day=01)
    return render_to_response(template, context)
