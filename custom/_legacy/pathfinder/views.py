from datetime import datetime
from dimagi.utils.couch.database import get_db
from dateutil.relativedelta import relativedelta
from patient_group import PathfinderPatientGroup
from dimagi.utils.parsing import string_to_datetime


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
    form_now = datetime(year, month, 1)+relativedelta(months=1)-relativedelta(seconds=1)
    pyear = 0
    pmonth = 0
    for result in user_ids:
        rform = result['doc']['form'] #shortcut
        try: # strptime() can fail if the CHW enters weird data.
            regdate = string_to_datetime(rform['patient']['date_of_registration'])
            if regdate > form_now:
                continue
        except:
            pass
        p = dict()
        age_tmp = string_to_datetime(rform['patient']['date_of_birth'])
        p['age'] = int((form_now - age_tmp).days / 365.25)
        p.update(rform['case'])
        p.update(rform['patient'])
        caseid_set.add(p['case_id'] )
        p['ward'] = p['village']
        p['registered_this_month'] = True if (regdate.year == form_now.year and regdate.month == form_now.month) else False
        p['followup_this_month'] = 0
        p['referrals_made'] = 0
        for i in ['provider',
                  'registration_and_followup_hiv',
                  'hiv_status_during_registration',
                  'hiv_status_after_test',
                  'referrals_hiv',
                  'ctc',
                  'medication_given',
                  'services',
                  'referrals']:
            if not i in p:
                p[i] = ''
        patients[p['case_id']] = p
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
    followup_keys = [[domain, x, year, month] for x in list(caseid_set)]
    followups = get_db().view('pathfinder/pathfinder_gov_followup_by_caseid', keys = followup_keys, include_docs=True).all()
    for f in followups:
        if not f['key'][1] in patients:
            continue
        p = patients[f['key'][1]]
        f = f['doc']['form']
        fp = f['patient']
        p['provider'] = f['meta']['userID']

        # The code below exists to hack around issues like people coming back to life after being dead,
        # multiple followups in a single month having different services, medication, and/or referral values,
        # and so on.

        if not p.has_key('registration_and_followup_hiv') or p['registration_and_followup_hiv'] == 'continuing' or p['registration_and_followup_hiv'] == '': # don't allow a value of 'dead' to change
            if fp.has_key('reg_followup'):
                p['registration_and_followup_hiv'] = fp['reg_followup']
        if p.has_key('followup_this_month'):
            p['followup_this_month'] += 1
        else:
            p['followup_this_month'] = 1
        if "medication_given" in fp and fp['medication_given']:
            p['medication_given'] += fp['medication_given'] + " "
        if "services_given" in fp and fp['services_given']:
            p['services'] += fp['services_given'] + " "
        if "any_referral" in fp and fp['any_referral'] == "yes":
            p['referrals'] += fp['referrals'] + " "
        p.update(fp)


def update_patients_with_referrals(patients, ids, year,month):
    """
    Given a set of patients, count how many completed referrals they had in that month.
    """
    refs = get_db().view('pathfinder/pathfinder_gov_referral', keys=[[x, int(year), int(month)] for x in list(ids)], include_docs=True).all()

    for p in patients: patients[p]['referrals_completed'] = 0
    for r in refs:
        if r['doc']['form']['client']['referral'] == 'yes':
            patients[r['doc']['form']['case']['case_id']]['referrals_completed'] += 1
