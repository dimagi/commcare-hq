from dimagi.utils.couch.database import get_db
from corehq.apps.domain.decorators import login_and_domain_required
from dimagi.utils.queryable_set import QueryableSet
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from functional import compose, partial, foldr
import functools


class PathfinderProvider(object):
    region = ""
    district =""
    ward = ""
    name = ""
    number = ""
    login_id = ""
    user_type = ""
    sex =""
    training = ""
    trainingorg = ""
    trainingdays = 0
    supervisorid = ""
    supervisorname = ""
    supervisorfacility = ""
    orgsupervisor = ""

class PathfinderPatient(object):
    case_id = ""
    provider = ""
    sex = ""
    ward = ""
    registration_cause = ""
    type_of_client = ""
    registration_and_followup_hiv = ""
    hiv_status_during_registration = ""
    referrals_hiv = ""
    registered_this_month = False
    followup_this_month = False
    latest_followup_form = ""
    ctc = ""
    def __unicode__(self):
        return self.case_id + \
               " ward:" + self.ward + \
               " sex:" + self.sex + \
               " cause:" + self.registration_cause + \
               " status:" + self.registration_and_followup_hiv
    def __repr__(self):
        return self.__unicode__()
    def __str__(self):
        return self.__unicode__()


class PathfinderPatientGroup(QueryableSet):
    def __init__(self):

        self._new = lambda x: x.registered_this_month
        self._followup = lambda x: x.followup_this_month

        self._hiv_reg = lambda x: x.registration_cause.count('hiv')

        self._hiv_pos = lambda x: x.hiv_status_during_registration == 'positive'
        self._hiv_neg = lambda x: x.hiv_status_during_registration == 'negative'
        self._hiv_unk = lambda x: x.hiv_status_during_registration == 'unknown'

        self._ctc_arv = lambda x: x.ctc == "registered_and_arvs"
        self._ctc_no_arv = lambda x: x.ctc == "registered_no_arvs"
        self._ctc_no_reg = lambda x: x.ctc == "not_registered"
                
        self._male = lambda x: x.sex == 'm'
        self._female = lambda x: x.sex == 'f'

        self._deaths = lambda x: x.registration_and_followup_hiv == 'dead'
        self._transfers = lambda x: x.registration_and_followup_hiv == 'transferred'
        self._continuing = lambda x: x.registration_and_followup_hiv == 'continuing'
        self._no_need = lambda x: x.registration_and_followup_hiv == 'no_need'
        self._opted_out = lambda x: x.registration_and_followup_hiv == 'no_need'

        self._vct = lambda x: x.referrals_hiv.count('counselling_and_testing') > 0
        self._ois = lambda x: x.referrals_hiv.count('opportunistic_infections') > 0
        self._ctc = lambda x: x.referrals_hiv.count('referred_to_ctc') > 0
        self._pmtct = lambda x: x.referrals_hiv.count('prevention_from_mother_to_child') > 0
        self._fp = lambda x: x.referrals_hiv.count('ref_fp') > 0
        self._sg = lambda x: x.referrals_hiv.count('other_services') > 0
        self._tb = lambda x: x.referrals_hiv.count('tb_clinic') > 0

def retrieve_providers(domain, ward):
    results = get_db().view('pathfinder/pathfinder_gov_chw', keys=[[domain, ward]]).all()
    chws = QueryableSet()
    for result in results:
        p = PathfinderProvider()
        (p.login_id, p.region, p.district, p.name, p.id, p.sex, p.training,
         p.trainingorg, p.trainingdays, p.user_type, p.supervisorname,
         p.supervisorfacility, p.supervisorid, p.orgsupervisor) = result['value']
        chws.add(p)
    return chws

def retrieve_patient_group(user_ids, domain, year, month):
    caseid_set = set()
    patients = {}
    for result in user_ids:
        pyear, pmonth = result['value'][1], result['value'][2]
        if pyear > year or (pyear == year and pmonth > month): # Exclude patients newer than this report.
            continue
        p = PathfinderPatient()
        p.case_id = result['value'][0]
        caseid_set.add(p.case_id)
        p.registration_cause = result['value'][3]
        p.sex = result['value'][4]
        p.ward = result['key'][1]
        p.registered_this_month = True if (result['value'][1] == year and (result['value'][2] + 1) == month) else False # months are 0-indexed
        patients[p.case_id] = p
    followup_keys = [[domain, year, month, x] for x in list(caseid_set)]
    followups = get_db().view('pathfinder/pathfinder_gov_followup_by_caseid', keys = followup_keys).all()
    for f in followups:
        p = patients[f['key'][3]]
        p.provider = f['value'][0]
        if p.registration_and_followup_hiv == 'continuing' or p.registration_and_followup_hiv == '': # don't allow a value of 'dead' to change
            p.registration_and_followup_hiv = f['value'][1]
        p.type_of_client = f['value'][2]
        p.referrals_hiv = f['value'][3]
        p.ctc = f[value]
        p.followup_this_month = True
    map(lambda x: patients.__delitem__(x), filter(lambda y: patients[y].followup_this_month == False, patients.keys()))
    gp = PathfinderPatientGroup()
    gp.update(patients.values())
    return gp

def ward_summary(domain, ward, year, month):
    # First, get all the registrations for the given ward.
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg', keys=[[domain, ward]]).all()
    return retrieve_patient_group(user_ids, domain, year, month)


def provider_summary(domain, username, year,month):
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg_by_username', keys=[[domain, username]]).all()
    return retrieve_patient_group(user_ids, domain, year, month)

#@login_and_domain_required
def home_based_care(request, domain, ward, year, month, template="pathfinder-reports/hbc.html"):
    context = RequestContext(request)
    user_ids = get_db().view('pathfinder/pathfinder_gov_reg', keys=[[domain, ward]]).all()
    context['p'] = retrieve_patient_group(user_ids, domain, year, month)
    return render_to_response(template, context)
