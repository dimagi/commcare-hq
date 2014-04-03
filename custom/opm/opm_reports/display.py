from datetime import datetime
from dimagi.utils.dates import months_between
from corehq.apps.reports.standard.cases.data_sources import CaseDisplay

EMPTY_FIELD = "---"

def get_property(dict_obj, name, default=None):
    if name in dict_obj:
        if type(dict_obj[name]) is dict:
            return dict_obj[name]["#value"]
        return dict_obj[name]
    else:
        return default if default is not None else EMPTY_FIELD

class MetDisplay(CaseDisplay):

    @property
    def child_age(self):
        dod = get_property(self.case, 'dod')
        if dod and dod != EMPTY_FIELD:
            dod = datetime.strptime(dod, '%Y-%m-%d')
            try:
                age = len(months_between(dod, datetime.now()))
            except AssertionError:
                age = -1
        else:
            age = -1
        return age

    @property
    def awc(self):
        return get_property(self.case, 'awc_name')

    @property
    def current_status(self):
        status = get_property(self.case, 'mother_preg_outcome')
        return 'mother' if status == '1' else 'pregnant'

    @property
    def month(self):
        if self.current_status == 'mother':
            if self.child_age != -1:
                return self.child_age
            else:
                return ''
        else:
            return get_property(self.case, 'pregnancy_month')

    @property
    def window(self):
        return get_property(self.case, 'which_window')

    @property
    def met_one(self):
        window_1_1 = get_property(self.case, 'window_1_1', '')
        window_1_2 = get_property(self.case, 'window_1_2', '')
        window_2_1 = get_property(self.case, 'window_2_1', '')
        window_2_2 = get_property(self.case, 'window_2_2', '')
        vhnd_3 = get_property(self.case, 'attendance_vhnd_3', '')
        vhnd_6 = get_property(self.case, 'attendance_vhnd_6', '')
        vhndattend = get_property(self.case, 'child1_vhndattend_calc', '')
        prev_vhndattend= get_property(self.case, 'prev_child1_vhndattend_calc', '')
        attendance_vhnd = get_property(self.case, 'child1_attendance_vhnd', '')
        if self.current_status == 'pregnant' and '1' in [window_1_1, window_1_2, window_2_1, window_2_2, vhnd_3, vhnd_6]:
            return True
        elif self.current_status == 'mother' and '1' in [vhndattend, prev_vhndattend, attendance_vhnd]:
            return True
        else:
            return False

    @property
    def met_two(self):
        weight_1 = get_property(self.case, 'weight_tri_1', '')
        prev_weight_1 = get_property(self.case, 'prev_weight_tri_1', '')
        weight_2 = get_property(self.case, 'weight_tri_2', '')
        prev_weight_2 = get_property(self.case, 'prev_weight_tri_2', '')
        preg_month = get_property(self.case, 'pregnancy_month', '')
        growthmon = get_property(self.case, 'child1_growthmon_calc', '')
        prev_growthmon = get_property(self.case, 'prev_child1_growthmon_calc', '')
        if self.current_status == 'pregnant' and ('1' in [weight_1, weight_2, prev_weight_1, prev_weight_2] or preg_month == '9'):
            return True
        elif self.current_status == 'mother' and '1' in [growthmon, prev_growthmon]:
            return True
        else:
            return False

    @property
    def met_four(self):
        breastfeed = get_property(self.case, 'child1_excl_breastfeed_calc', '')
        prev_breastfeed = get_property(self.case, 'prev_child1_excl_breastfeed_calc', '')
        if self.current_status == 'mother' and self.child_age == 6 and ('1' in [breastfeed, prev_breastfeed]):
            return True
        return False

    @property
    def met_five(self):
        ors = get_property(self.case, 'child1_ors_calc', '')
        prev_ors = get_property(self.case, 'prev_child1_ors_calc', '')
        if self.current_status == 'mother' and self.child_age in [6, 9, 12] and '1' in [ors, prev_ors]:
            return True
        return False

    @property
    def one(self):
        mpo = get_property(self.case, 'mother_preg_outcome')
        pregnancy_month = get_property(self.case, 'pregnancy_month')
        if (mpo == "" and pregnancy_month == '9') or (mpo == '1' and 0 <= self.child_age <= 1):
            return '<img class="img-report" src="/static/opm/img/met_y.png">'
        else:
            return '<img class="img-report" src="/static/opm/img/met_n.png">'

    @property
    def two(self):
        pregnancy_month = get_property(self.case, 'pregnancy_month')
        if self.current_status == 'pregnant' and (pregnancy_month == '6' or pregnancy_month == '9'):
            return '<img class="img-report" src="/static/opm/img/preg_y.png">'
        elif self.current_status == 'mother' and self.child_age % 3 == 0:
            return '<img class="img-report" src="/static/opm/img/preg_y.png">'
        else:
            return ''

    @property
    def four(self):
        if self.current_status == 'mother' and self.child_age == 6:
            return "Yes"
        return "No"

    @property
    def five(self):
        suffer = True if get_property(self.case, "child1_suffer_diarrhea", '') == '1' else False
        if self.current_status == 'mother' and self.child_age in [6, 9, 12] and suffer:
            return "Yes"
        return "No"


class AtriDisplay(MetDisplay):

    @property
    def husband_name(self):
        return get_property(self.case, 'husband_name')

    @property
    def met_three(self):
        if self.current_status == 'mother':
            if self.child_age == 3 and (get_property(self.case, 'child1_weight_calc', '') or get_property(self.case, 'prev_child1_weight_calc', '')):
                return True
            if self.child_age == 6 and (get_property(self.case, 'child1_register_calc', '') or get_property(self.case, 'prev_child1_register_calc', '')):
                return True
            if self.child_age == 9 and (get_property(self.case, 'child1_measles_calc', '') or get_property(self.case, 'prev_child1_measles_calc', '')):
                return True
        return False

    @property
    def three(self):
        pregnancy_month = get_property(self.case, 'pregnancy_month')
        if self.current_status == 'pregnant' and pregnancy_month == '7':
            return '<img class="img-report" src="/static/opm/img/tablets_y.png">'
        elif self.current_status == 'mother' and self.child_age in [3, 6, 12]:
            return '<img class="img-report" src="/static/opm/img/tablets_y.png">'
        else:
            return ''



    @property
    def cash_to_transferred(self):
        if self.met_one or self.met_two or self.met_three or self.met_four or self.met_five:
            return '<span style="color: green;">Rs. 250</span>'
        return '<span style="color: red;">Rs. 0</span>'


class WazirganjDisplay(MetDisplay):

    def __init__(self, report, case_dict):
        super(WazirganjDisplay, self).__init__(report, case_dict)

    @property
    def cash_to_transferred(self):
        if self.met_one or self.met_two or self.met_four or self.met_five:
            return '<span style="color: green;">Rs. 250</span>'
        return '<span style="color: red;">Rs. 0</span>'