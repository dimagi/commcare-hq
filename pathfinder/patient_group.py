from dimagi.utils.queryable_set import QueryableList

class PathfinderPatientGroup(QueryableList):
    def __init__(self):

        self._new = lambda x: x['registered_this_month']
        self._old = lambda x: not x['registered_this_month']

        self._followup = lambda x: x['followup_this_month']

        self._f = lambda x: x['followup_this_month'] and (x['registration_and_followup_hiv'] == 'continuing' or x['registration_and_followup_hiv'] == '')


        self._0to14 = lambda x: 0 <= x['age'] <= 14
        self._15to24 = lambda x: 15 <= x['age'] <= 24
        self._25to49 = lambda x: 25 <= x['age'] <= 49
        self._50plus = lambda x: 50 <= x['age']
        self._child = lambda x: 18 > x['age']
        self._adult = lambda x: 18 <= x['age']

        self._hiv_reg = lambda x: x.has_key('registration_cause') and x['registration_cause'].count('hiv')

        self._hiv_unk = lambda x: (not x['registration_cause'].count('hiv')) and (x['hiv_status_during_registration'] is None or \
                                    (x['hiv_status_during_registration'].lower() != 'positive' and \
                                    x['hiv_status_during_registration'].lower() != 'negative')) \
                                    and \
                                    (x['hiv_status_after_test'].lower() is None or \
                                    (x['hiv_status_after_test'].lower() != 'positive' and \
                                    x['hiv_status_after_test'].lower() != 'negative'))
        self._hiv_pos = lambda x: (x['hiv_status_during_registration'].lower() == 'positive' or  x['hiv_status_after_test'].lower() == 'positive')
        self._hiv_neg = lambda x: x['hiv_status_during_registration'].lower() != 'positive' and  x['hiv_status_after_test'].lower() == 'negative'

        self._cip = lambda x: not self._hiv_pos(x)

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