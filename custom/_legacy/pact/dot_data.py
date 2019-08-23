from __future__ import absolute_import
from __future__ import unicode_literals
import logging
from functools import cmp_to_key

from django.conf import settings
from pytz import timezone
from datetime import datetime, timedelta, date
from pact.enums import (
    CASE_ART_REGIMEN_PROP,
    CASE_NONART_REGIMEN_PROP,
    DAY_SLOTS_BY_TIME,
    DOT_ART,
    DOT_DAYS_INTERVAL,
    DOT_NONART,
    DOT_OBSERVATION_DIRECT,
    DOT_UNCHECKED_CELL,
)

from pact.models import CObservation
from six.moves import range


class DOTDayDose(object):
    drug_class = None  # DOT_ART, DOT_NONART
    total_doses = 0

    def __init__(self, drug_class):
        self.drug_class = drug_class
        self.total_doses_hist = {}  # debug tool
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

        # debug, double check for weird data
        if 'obs.total_doses' not in self.total_doses_hist:
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
            dot_day_dose = self.art
        else:
            dot_day_dose = self.nonart
        dot_day_dose.update_total_doses(obs)
        dot_day_dose.add_obs(obs)

    @classmethod
    def merge_from_observations(cls, day_observations):
        """
        Receive an array of CObservations and try to priority sort them
        and make a json-able array of ART and NON ART submissions
        for DOT calendar display.
        This is an intermediate, more semantically readable markup
        for preparing/merging data.
        This is not the final form that's transmitted to/from phones.
        """
        dot_day = cls()

        for obs in day_observations:
            dot_day.update_dosedata(obs)
        dot_day.sort_all_observations()
        return dot_day

    def to_case_json(self, casedoc, regimen_labels):
        """
        Return the json representation of a single days nonart/art data
        that is put back into the caseblock, sent to phone,
        sent back from phone

        This is the transmitted representation
        and the phone's representation of DOT data.
        """

        def get_obs_for_dosenum(obs_list, dose_num, label):
            if len(obs_list) > 0:
                obs = obs_list[0]
                day_slot = label
                if obs.day_slot != '' and obs.day_slot is not None:
                    day_slot = obs.day_slot
                if (obs.day_note is not None and len(obs.day_note) > 0
                        and obs.day_note != "[AddendumEntry]"):
                    day_note = obs.day_note
                else:
                    day_note = ''

                return [obs.adherence, obs.method, day_note, day_slot]
                # one and done per array
            else:
                # return pristine unchecked
                return ['unchecked', 'pillbox', '', label]

        ret = []
        for ix, dose_data in enumerate([self.nonart, self.art]):
            drug_arr = []
            labels_arr = regimen_labels[ix]
            dose_nums = list(dose_data.dose_dict.keys())
            dose_nums.sort()

            for dose_num in dose_nums:
                if dose_num is not None:
                    # for each dose num in the observed array of the drug type,
                    # there maybe more than one observation
                    obs_list = dose_data.dose_dict[dose_num]
                    drug_arr.append(get_obs_for_dosenum(obs_list, dose_num, labels_arr[dose_num]))
                else:
                    # just to get a sense of how widespread this problem is in sentry
                    logging.error('A pact case had an empty dose number.')

            # don't fill because we're looking at what was submitted.
            if len(drug_arr) <= dose_data.total_doses:
                if dose_data.drug_class == DOT_NONART:
                    max_doses = int(getattr(casedoc, 'nonartregimen', None) or 0)
                elif dose_data.drug_class == DOT_ART:
                    max_doses = int(getattr(casedoc, 'artregimen', None) or 0)

                # hack, in cases where we have zero data, put in the current regimen delta count
                delta = max_doses - dose_data.total_doses
                for x in range(0, delta):
                    drug_arr.append(["unchecked", "pillbox", '', labels_arr[x] if x < len(labels_arr) else -1])
            ret.append(drug_arr)
        return ret


def filter_obs_for_day(this_date, observations):
    assert this_date.__class__ == date
    ret = [x for x in observations if x['observed_date'].date() == this_date]

    return ret


def query_observations(case_id, start_date, end_date):
    """
    Hit couch to get the CObservations for the given date range of the OBSERVED dates.
    These are the actual observation day cells in which they filled in DOT data.
    args: start_date and end_date as datetime objects
    """
    startkey = [case_id, 'anchor_date', start_date.year, start_date.month, start_date.day]
    endkey = [case_id, 'anchor_date', end_date.year, end_date.month, end_date.day]
    observations = CObservation.view('pact/dots_observations',
                                     startkey=startkey, endkey=endkey).all()
    return observations


def query_observations_singledoc(doc_id):
    """
    Hit couch to get the CObservations for a single xform submission
    """
    key = ['doc_id', doc_id]
    observations = CObservation.view('pact/dots_observations', key=key,
                                     classes={None: CObservation}).all()
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
    x_is_reconciliation = getattr(x, 'is_reconciliation', None)
    y_is_reconciliation = getattr(y, 'is_reconciliation', None)
    # Reconciliation handling
    # reconciliations always win.
    if x_is_reconciliation and y_is_reconciliation:
        # sort by earlier date, so flip x,y
        return cmp(y.submitted_date, x.submitted_date)
    elif x_is_reconciliation and not y_is_reconciliation:
        # result: x > y
        return 1
    elif not x_is_reconciliation and y_is_reconciliation:
        # result: x < y
        return -1
    elif x.method == DOT_OBSERVATION_DIRECT and y.method == DOT_OBSERVATION_DIRECT:
        # Direct observations win next
        # sort by earlier date, so flip x,y
        return cmp(y.encounter_date, x.encounter_date)
    elif x.method == DOT_OBSERVATION_DIRECT and y.method != DOT_OBSERVATION_DIRECT:
        # result: x > y
        return 1
    elif x.method != DOT_OBSERVATION_DIRECT and y.method == DOT_OBSERVATION_DIRECT:
        # result: x < y
        return -1
    elif (x.adherence, x.method) == DOT_UNCHECKED_CELL and (y.adherence, y.method) != DOT_UNCHECKED_CELL:
        # unchecked should always lose
        return -1
    elif (x.adherence, x.method) != DOT_UNCHECKED_CELL and (y.adherence, y.method) == DOT_UNCHECKED_CELL:
        return 1
    else:
        return cmp(y.encounter_date, x.encounter_date)


def sort_observations(observations):
    """
    Method to sort observations to make sure that the "winner" is at index 0
    """
    return sorted(observations, key=cmp_to_key(cmp_observation), reverse=True)


def get_dots_case_json(casedoc, anchor_date=None):
    """
    Return JSON-ready array of the DOTS block for given patient.
    Pulling properties from PATIENT document.
    Patient document trumps casedoc in this use case.
    """

    if anchor_date is None:
        anchor_date = datetime.now(tz=timezone(settings.TIME_ZONE))
    enddate = anchor_date
    ret = {
        'regimens': [
            # non art is 0
            int(getattr(casedoc, CASE_NONART_REGIMEN_PROP, None) or 0),
            # art is 1
            int(getattr(casedoc, CASE_ART_REGIMEN_PROP, None) or 0),
        ],
        'regimen_labels': [
            list(casedoc.nonart_labels),
            list(casedoc.art_labels)
        ],
        'days': [],
        # dmyung - hack to have query_observations timezone
        # be relative specific to the eastern seaboard
        'anchor': anchor_date.strftime("%d %b %Y"),
    }

    observations = query_observations(
        casedoc._id, enddate-timedelta(days=DOT_DAYS_INTERVAL), enddate)
    for delta in range(DOT_DAYS_INTERVAL):
        obs_date = enddate - timedelta(days=delta)
        day_arr = filter_obs_for_day(obs_date.date(), observations)
        day_data = DOTDay.merge_from_observations(day_arr)
        ret['days'].append(day_data.to_case_json(casedoc, ret['regimen_labels']))

    ret['days'].reverse()
    return ret
