import logging
import pdb
import dateutil
from django.conf import settings
from datetime import datetime, timedelta
from pytz import timezone
from pact.enums import DAY_SLOTS_BY_TIME, DOT_DAYS_INTERVAL, DOT_ART, DOT_NONART, CASE_ART_REGIMEN_PROP, CASE_NONART_REGIMEN_PROP

from datetime import date
from pact.enums import    DOT_OBSERVATION_DIRECT
from pact.models import CObservation


class DOTDayDose(object):
    drug_class=None #DOT_ART, DOT_NONART
    total_doses = 0

    def __init__(self, drug_class):
        self.drug_class=drug_class
        self.total_doses_hist = {} # debug tool
        self.dose_dict = {}

    def has_obs(self, obs):
        if self.dose_dict.get(obs.dose_number, None) is None:
            return False
        else:
            return True

    def add_obs(self, obs):
        if not self.has_obs(obs):
            self.dose_dict[obs.dose_number] = []
        self.dose_dict[obs.dose_number].append(obs)

    def update_total_doses(self, obs):
        if self.total_doses < obs.total_doses:
            self.total_doses = obs.total_doses

        #debug, double check for weird data
        if not self.total_doses_hist.has_key(obs.total_doses):
            self.total_doses_hist[obs.total_doses] = []
        self.total_doses_hist[obs.total_doses].append(obs)

class DOTDay(object):
    nonart = None
    art = None

    def __init__(self):
        self.nonart = DOTDayDose(DOT_NONART)
        self.art = DOTDayDose(DOT_ART)

    def sort_all_observations(self):
        for day_doses in [self.nonart, self.art]:
            dose_dict = day_doses.dose_dict
            for dose_num in dose_dict.keys():
                observations = dose_dict[dose_num]
                dose_dict[dose_num] = sort_observations(observations)


    def update_dosedata(self, obs):
        if obs.is_art:
            drug_attr = 'art'
        else:
            drug_attr='nonart'
        getattr(self,drug_attr).update_total_doses(obs)
        if not getattr(self, drug_attr).has_obs(obs):
            getattr(self, drug_attr).add_obs(obs)

    @classmethod
    def merge_from_observations(cls, day_observations):
        """
        Receive an array of CObservations and try to priority sort them and make a json-able array of ART and NON ART submissions for DOT calendar display.
        This is an intermiary, more semantically readable markup for preparing/merging data. This is not the final form that's transmitted to/from phones.
        """
        dot_day = cls()

        for obs in day_observations:
            dot_day.update_dosedata(obs)
        dot_day.sort_all_observations()
        return dot_day


    def to_case_json(self, casedoc):
#        pass
#    def get_day_elements(casedoc, day_data):
        """
        Return the json representation of a single days nonart/art data that is put back into the caseblock, sent to phone, sent back from phone

        This is the transmitted representation and the phone's representation of DOT data.
        """
        ret = []
#        for drug_type in [DOT_NONART,DOT_ART]:
        for dose_data in [self.nonart, self.art]:
            drug_arr = []
            #for dose_num, obs_list in day_data[drug_type]['dose_dict'].items():
            dose_nums = dose_data.dose_dict.keys()
            dose_nums.sort()
            for dose_num in dose_nums:
                obs_list = dose_data.dose_dict[dose_num]
                for obs in obs_list:
                    day_slot = -1
                    if obs.day_slot != '' and obs.day_slot is not None:
                        day_slot = obs.day_slot
                    if obs.day_note != None and len(obs.day_note) > 0 and obs.day_note != "[AddendumEntry]":
                        day_note = obs.day_note
                    else:
                        day_note = ''

                    drug_arr.append([obs.adherence, obs.method, day_note, day_slot]) #todo, add regimen_item
                    #one and done per array
                    break

            #don't fill because we're looking at what was submitted.
            if len(drug_arr) <= dose_data.total_doses:
                if dose_data.drug_class == DOT_NONART:
                    max_doses = int(casedoc.nonartregimen)
                elif dose_data.drug_class == DOT_ART:
                    max_doses = int(casedoc.artregimen)

                #hack, in cases where we have zero data, put in the current regimen delta count
                delta = max_doses - dose_data.total_doses
                for x in range(0, delta):
                    drug_arr.append(["unchecked", "pillbox", '', -1])
            ret.append(drug_arr)
        return ret



def filter_obs_for_day(this_date, observations):
    assert this_date.__class__ == date
    #todo, normalize for timezone
    ret = filter(lambda x: x['observed_date'].date() == this_date, observations)
    return ret


def query_observations(case_id, start_date, end_date):
    """
    Hit couch to get the CObservations for the given date range of the OBSERVED dates.
    These are the actual observation day cells in which they filled in DOT data.
    """
    startkey = [case_id, 'observe_date', start_date.year, start_date.month, start_date.day]
    endkey = [case_id, 'observe_date', end_date.year, end_date.month, end_date.day]
    observations = CObservation.view('pact/dots_observations', startkey=startkey, endkey=endkey).all()
    return observations

def query_observations_singledoc(doc_id):
    """
    Hit couch to get the CObservations for a single xform submission
    """
    key = ['doc_id', doc_id]
    observations = CObservation.view('pact/dots_observations', key=key).all()
    return observations

def cmp_observation(x, y):
    """
    for a given COBservation, do the following.
    1: If it's an addendum/reconciliation trumps all
    2: If it's direct, and other is not direct, the direct wins
    3: If both direct, do by earliest date
    4: If neither direct, do by earliest encounter_date regardless of method.

    < -1
    = 0
    > 1

    Assumes that x and y have the same observation date (cell in the DOT json array)
    Encounter date is the date in which the date cell is observed.
    """

    assert x.observed_date.date() == y.observed_date.date()
    #Reconcilation handling
    if (hasattr(x, 'is_reconciliation') and getattr(x, 'is_reconciliation')) and (hasattr(y, 'is_reconciliation') and getattr(y, 'is_reconciliation')):
        #sort by earlier date, so flip x,y
        return cmp(y.submitted_date, x.submitted_date)

    elif (hasattr(x, 'is_reconciliation') and getattr(x, 'is_reconciliation')) and (not hasattr(y,'is_reconciliation') or not getattr(y, 'is_reconciliation')):
        # result: x > y
        return 1
    elif (not hasattr(x, 'is_reconciliation') or not getattr(x, 'is_reconciliation')) and (hasattr(y, 'is_reconciliation') and getattr(y, 'is_reconciliation')):
        # result: x < y
        return -1

    if x.method == DOT_OBSERVATION_DIRECT and y.method == DOT_OBSERVATION_DIRECT:
        #sort by earlier date, so flip x,y
        return cmp(y.encounter_date, x.encounter_date)
    elif x.method == DOT_OBSERVATION_DIRECT and y.method != DOT_OBSERVATION_DIRECT:
        #result: x > y
        return 1
    elif x.method != DOT_OBSERVATION_DIRECT and y.method == DOT_OBSERVATION_DIRECT:
        #result: x < y
        return -1
    else:
        #sort by earlier date, so flip x,y
        return cmp(y.encounter_date, x.encounter_date)

def sort_observations(observations):
    """
    Method to sort observations to make sure that the "winner" is at index 0
    """
    return sorted(observations, cmp=cmp_observation, reverse=True) #key=lambda x: x.created_date, reverse=True)



def isodate_string(date):
    if date: return dateutil.datetime_isoformat(date) + "Z"
    return ""

def get_regimen_code_arr(str_regimen):
    """
    Helper function to decode regimens for both the old style regimens (in REGIMEN_CHOICES) as well as the new style
    regimens as required in the technical specs above.

    should return an array of day slot indices.
    """
    if str_regimen is None or str_regimen == '' or str_regimen == 'None':
        return []


    #legacy handling
    if str_regimen.lower() == 'qd':
        return [0]
    elif str_regimen.lower() == 'qd-am':
        return [0]
    elif str_regimen.lower() == 'qd-pm':
        return [2]
    elif str_regimen.lower() == 'bid':
        return [0, 2]
    elif str_regimen.lower() == 'qid':
        return [0, 1, 2, 3]
    elif str_regimen.lower() == 'tid':
        return [0, 1, 2]
    elif str_regimen.lower() == '':
        return []

    #newer handling, a split string
    splits = str_regimen.split(',')
    ret = []
    for x in splits:
        if x in DAY_SLOTS_BY_TIME.keys():
            ret.append(DAY_SLOTS_BY_TIME[x])
        else:
            logging.error("value error, the regimen string is incorrect for the given patient, returning blank")
            ret = []
    return ret

def get_dots_case_json(casedoc, anchor_date=None):
    """
    Return JSON-ready array of the DOTS block for given patient.
    Pulling properties from PATIENT document.  patient document trumps casedoc in this use case.
    """

    if anchor_date is None:
        anchor_date = datetime.now(tz=timezone(settings.TIME_ZONE))
    enddate = anchor_date
    ret = {}

    ret['regimens'] = [
        int(getattr(casedoc, CASE_NONART_REGIMEN_PROP, 0)), #non art is 0
        int(getattr(casedoc, CASE_ART_REGIMEN_PROP, 0)), #art is 1
    ]
    ret['regimen_labels'] = [
        list(casedoc.nonart_labels),
        list(casedoc.art_labels)
    ]

    ret['days'] = []
    #dmyung - hack to have query_observations be timezone be relative specific to the eastern seaboard
    #ret['anchor'] = isodate.strftime(datetime.now(tz=timezone(settings.TIME_ZONE)), "%d %b %Y")
    ret['anchor'] = anchor_date.strftime("%d %b %Y")

    observations = query_observations(casedoc._id, enddate-timedelta(days=DOT_DAYS_INTERVAL),enddate)
    for delta in range(DOT_DAYS_INTERVAL):
        obs_date = enddate - timedelta(days=delta)
        day_arr = filter_obs_for_day(obs_date.date(), observations)
        day_data = DOTDay.merge_from_observations(day_arr)
        ret['days'].append(day_data.to_case_json(casedoc))
    ret['days'].reverse()
    return ret



def calculate_regimen_caseblock(case):
    """
    Forces all labels to be reset back to the labels set on the patient document.
    patient document trumps casedoc in this case.
    """
    update_ret = {}
    for prop_fmt in ['dot_a_%s', 'dot_n_%s']:
        if prop_fmt[4] == 'a':
            code_arr = get_regimen_code_arr(case.art_regimen)
            update_ret['artregimen'] = str(len(code_arr)) if len(code_arr) > 0 else ""
        elif prop_fmt[4] == 'n':
            code_arr = get_regimen_code_arr(case.non_art_regimen)
            update_ret['nonartregimen'] = str(len(code_arr)) if len(code_arr) > 0 else ""
        digit_strings = ["zero", 'one', 'two', 'three','four']
        for x in range(1,5):
            prop_prop = prop_fmt % digit_strings[x]
            if x > len(code_arr):
                update_ret[prop_prop] = ''
            else:
                update_ret[prop_prop] = str(code_arr[x-1])
    return update_ret
