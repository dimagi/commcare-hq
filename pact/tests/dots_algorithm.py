from datetime import datetime, timedelta
import random
from django.test import TestCase
from pact.dot_data import cmp_observation, sort_observations
from pact.enums import DOT_ADHERENCE_EMPTY, DOT_OBSERVATION_DIRECT, DOT_OBSERVATION_PILLBOX, DOT_OBSERVATION_SELF
from pact.models import CObservation


def _observationGenerator(encounter_date, observation_date, adherence=DOT_ADHERENCE_EMPTY):
    return CObservation(encounter_date=encounter_date,
                        observed_date=observation_date,
                        adherence=adherence,)

def generateDirect(encounter_date, observation_date, adherence=DOT_ADHERENCE_EMPTY):
    obs = _observationGenerator(encounter_date,observation_date, adherence=adherence)
    obs.method=DOT_OBSERVATION_DIRECT
    return obs

def generateReconciliation():
    pass

def generatePillbox(encounter_date, observation_date, adherence=DOT_ADHERENCE_EMPTY):
    obs = _observationGenerator(encounter_date,observation_date, adherence=adherence)
    obs.method=DOT_OBSERVATION_PILLBOX
    return obs

def generateSelf(encounter_date, observation_date, adherence=DOT_ADHERENCE_EMPTY):
    obs = _observationGenerator(encounter_date,observation_date, adherence=adherence)
    obs.method=DOT_OBSERVATION_SELF
    return obs

def generateAny(encounter_date, observation_date, adherence=DOT_ADHERENCE_EMPTY):
    obs = _observationGenerator(encounter_date,observation_date, adherence=adherence)
    obs.method=random.choice([DOT_OBSERVATION_PILLBOX, DOT_OBSERVATION_PILLBOX])
    return obs

class dotsAlgorithmTests(TestCase):
    def setUp(self):

        self.observed_date = datetime.utcnow()
        self.encounter_dates = [datetime.utcnow() - timedelta(days=2), datetime.utcnow()-timedelta(days=1)]
        pass


    def testDirectTrumpsAll(self):

        direct = generateDirect(self.encounter_dates[0], self.observed_date)
        self_report = generateSelf(self.encounter_dates[0], self.observed_date)

        self.assertEqual(cmp_observation(direct, self_report), 1)
        self.assertEqual(cmp_observation(self_report, direct), -1)


    def testDirects(self):
        direct = generateDirect(self.encounter_dates[0], self.observed_date)
        direct_later = generateDirect(self.encounter_dates[1], self.observed_date)

        self.assertEqual(cmp_observation(direct, direct_later), 1)
        self.assertEqual(cmp_observation(direct_later, direct), -1)


    def testNonDirects(self):
        #by date
        self_first = generateSelf(self.encounter_dates[0], self.observed_date)
        self_second = generateSelf(self.encounter_dates[1], self.observed_date)
        self.assertEqual(cmp_observation(self_second, self_first), -1)
        self.assertEqual(cmp_observation(self_first, self_second), 1)

        pillbox_first = generateSelf(self.encounter_dates[0], self.observed_date)
        pillbox_second = generateSelf(self.encounter_dates[1], self.observed_date)

        self.assertEqual(cmp_observation(pillbox_second, pillbox_first), -1)
        self.assertEqual(cmp_observation(pillbox_first, pillbox_second), 1)

        self.assertEqual(cmp_observation(self_second, pillbox_first), -1)
        self.assertEqual(cmp_observation(self_first, pillbox_second), 1)

        self.assertEqual(cmp_observation(self_second, self_second), 0)
        self.assertEqual(cmp_observation(self_first, pillbox_first), 0)
        self.assertEqual(cmp_observation(pillbox_first, self_first), 0)

    def testReconciliationTrumps(self):
        pass

    def testSorting(self):
        num = 8
        observed_date = datetime.utcnow()
        encounter_dates = [datetime.utcnow()-timedelta(days=x) for x in range(num)]



        #whole bunch of others

        no_direct = [generateAny(x, observed_date) for x in encounter_dates]
        no_direct_winner = no_direct[-1] #earliest is last

        random.shuffle(no_direct)
        no_direct_sorted = sort_observations(no_direct)

        self.assertEqual(no_direct_winner.encounter_date, no_direct_sorted[0].encounter_date)


        #at least one direct
        direct = generateDirect(datetime.utcnow() + timedelta(days=random.randint(-100,100)), observed_date)
        with_direct = [generateAny(x, observed_date) for x in encounter_dates] + [direct]
        random.shuffle(with_direct)

        with_direct_sorted = sort_observations(with_direct)
        self.assertEqual(direct.encounter_date, with_direct_sorted[0].encounter_date)
        self.assertEqual(direct.method, with_direct_sorted[0].method)







    #basic test cases for the merging of dots data - no Couch involved

