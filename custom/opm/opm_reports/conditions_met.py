import datetime
from dimagi.utils.dates import months_between
from corehq.apps.users.models import CommCareCase
from custom.opm.opm_reports.constants import InvalidRow

EMPTY_FIELD = "---"
M_ATTENDANCE_Y = 'attendance_vhnd_y.png'
M_ATTENDANCE_N = 'attendance_vhnd_n.png'
C_ATTENDANCE_Y = 'child_attendance_vhnd_y.png'
C_ATTENDANCE_N = 'child_attendance_vhnd_n.png'
M_WEIGHT_Y = 'mother_weight_y.png'
M_WEIGHT_N = 'mother_weight_n.png'
C_WEIGHT_Y = 'child_weight_y.png'
C_WEIGHT_N = 'child_weight_n.png'
MEASLEVACC_Y = 'child_child_measlesvacc_y.png'
MEASLEVACC_N = 'child_child_measlesvacc_n.png'
C_REGISTER_Y = 'child_child_register_y.png'
C_REGISTER_N = 'child_child_register_n.png'
CHILD_WEIGHT_Y = 'child_weight_2_y.png'
CHILD_WEIGHT_N = 'child_weight_2_n.png'
IFA_Y = 'ifa_receive_y.png'
IFA_N = 'ifa_receive_n.png'
EXCBREASTFED_Y = 'child_child_excbreastfed_y.png'
EXCBREASTFED_N = 'child_child_excbreastfed_n.png'
ORSZNTREAT_Y = 'child_orszntreat_y.png'
ORSZNTREAT_N = 'child_orszntreat_n.png'
GRADE_NORMAL_Y = 'grade_normal_y.png'
GRADE_NORMAL_N = 'grade_normal_n.png'
SPACING_PROMPT_Y = 'birth_spacing_prompt_y.png'
SPACING_PROMPT_N = 'birth_spacing_prompt_n.png'


class ConditionsMet(object):

    method_map = {
        "atri": [
            ('name', "List of Beneficiary", True),
            ('awc_name', "AWC Name", True),
            ('husband_name', "Husband Name", True),
            ('month', "Month", True),
            ('window', "Window", True),
            ('one', "1", True),
            ('two', "2", True),
            ('three', "3", True),
            ('four', "4", True),
            ('five', "5", True),
            ('cash', "Cash to be transferred", True),
            ('owner_id', "Owner Id", False),
            ('block_name', "Block Name", False),
            ('closed', 'Closed', False)
        ],
        'wazirganj': [
            ('name', "List of Beneficiary", True),
            ('awc_name', "AWC Name", True),
            ('status', "Current status", True),
            ('month', "Month", True),
            ('window', "Window", True),
            ('one', "1", True),
            ('two', "2", True),
            ('four', "3", True),
            ('five', "4", True),
            ('cash', "Cash to be transferred", True),
            ('owner_id', "Owner Id", False),
            ('block_name', "Block Name", False),
            ('closed', 'Closed', False)
        ]
    }

    def __init__(self, case, report):
        if report.snapshot is not None:
            report.filter(
                lambda key: case['_source'][key],
                # case.awc_name, case.block_name
                [('awc_name', 'awcs'), ('block_name', 'block'), ('owner_id', 'gp'), ('closed', 'is_open')],
            )
        img_elem = '<div style="width:100px !important;"><img src="/static/opm/img/%s"></div>'

        met = {
            'window_1_1': None,
            'window_1_2': None,
            'window_2_1': None,
            'window_2_2': None,
            'attendance_vhnd_3': None,
            'attendance_vhnd_6': None,
            'child1_vhndattend_calc': None,
            'prev_child1_vhndattend_calc': None,
            'child1_attendance_vhnd': None,
            'weight_tri_1': None,
            'prev_weight_tri_1': None,
            'weight_tri_2': None,
            'prev_weight_tri_2': None,
            'child1_growthmon_calc': None,
            'prev_child1_growthmon_calc': None,
            'child1_excl_breastfeed_calc': None,
            'prev_child1_excl_breastfeed_calc': None,
            'child1_ors_calc': None,
            'prev_child1_ors_calc': None,
            'child1_weight_calc': None,
            'child1_register_calc': None,
            'child1_measles_calc': None,
            'prev_child1_weight_calc': None,
            'prev_child1_register_calc': None,
            'prev_child1_measles_calc': None,
            'child1_suffer_diarrhea': None,
            'interpret_grade_1': None
        }

        def get_property(obj, name, default=None):
            if name in obj:
                if type(obj[name]) is dict:
                    return obj[name]
                return obj[name]
            else:
                return default if default is not None else EMPTY_FIELD

        def get_property_from_forms(forms, met_properties):
            for form in forms:
                for k, v in met_properties.iteritems():
                    if k == 'child1_suffer_diarrhea':
                        if 'child_1' in form.form and k in form.form['child_1']:
                            met_properties[k] = form.form['child_1'][k]
                    else:
                        if k in form.form:
                            met_properties[k] = form.form[k]
            return met_properties

        case_obj = CommCareCase.get(case['_source']['_id'])
        self.block_name = get_property(case_obj, 'block_name', '')
        self.owner_id = get_property(case_obj, 'owner_id', '')
        self.closed = get_property(case_obj, 'closed', False)
        forms = case_obj.get_forms()
        birth_spacing_prompt = []
        for form in forms:
            if 'birth_spacing_prompt' in form.form:
                birth_spacing_prompt.append(form.form['birth_spacing_prompt'])

        filtered_forms = [form for form in case_obj.get_forms() if report.datespan.startdate <= form.received_on <= report.datespan.enddate]

        get_property_from_forms(filtered_forms, met)

        dod = get_property(case_obj, 'dod')
        if dod and dod != EMPTY_FIELD:
            try:
                child_age = len(months_between(datetime.datetime(dod.year, dod.month, dod.day), datetime.datetime.now()))
            except AssertionError:
                child_age = -1
        else:
            child_age = -1

        if get_property(case_obj, 'mother_preg_outcome', '') == '1':
            self.status = 'mother'
        elif get_property(case_obj, 'mother_preg_outcome', '') == '':
            self.status = 'pregnant'
        else:
            raise InvalidRow

        met_one = False
        met_two = False
        met_three = False
        met_four = False
        met_five = False
        preg_month = get_property(case_obj, 'pregnancy_month', 0) or 0
        if self.status == 'pregnant':
            if '1' in [met['window_1_1'], met['window_1_2'], met['window_2_1'], met['window_2_2'], met['attendance_vhnd_3'], met['attendance_vhnd_6']]:
                met_one = True
            if (preg_month == '6' and '1' in [met['weight_tri_1'], met['prev_weight_tri_1']]) or (preg_month == '9' and '1' in [met['weight_tri_2'], met['prev_weight_tri_2']]):
                met_two = True
        elif self.status == 'mother':
            if '1' in [met['child1_vhndattend_calc'], met['prev_child1_vhndattend_calc'], met['child1_attendance_vhnd']]:
                met_one = True
            if '1' in [met['child1_growthmon_calc'], met['prev_child1_growthmon_calc']]:
                met_two = True
            if (child_age == 3 and (met['child1_weight_calc'] or met['prev_child1_weight_calc'])) or \
                    (child_age == 6 and (met['child1_register_calc'] or met['prev_child1_register_calc'])) or \
                    (child_age == 9 and (met['child1_measles_calc'] or met['prev_child1_measles_calc'])):
                met_three = True
            if child_age == 6 and ('1' in [met['child1_excl_breastfeed_calc'], met['prev_child1_excl_breastfeed_calc']]):
                met_four = True
            if child_age in [6, 9, 12] and '1' in [met['child1_ors_calc'], met['prev_child1_ors_calc']]:
                met_five = True

        self.name = get_property(case_obj, 'name')
        self.awc_name = get_property(case_obj, 'awc_name')
        self.husband_name = get_property(case_obj, 'husband_name')
        self.window = get_property(case_obj, 'which_window')
        if self.status == 'pregnant':
            self.month = get_property(case_obj, 'pregnancy_month')
            self.one = img_elem % M_ATTENDANCE_Y if preg_month == '9' else img_elem % M_ATTENDANCE_N
            self.two = img_elem % M_WEIGHT_Y if preg_month in ['6', '9'] else img_elem % M_WEIGHT_N
            self.three = img_elem % IFA_Y if int(preg_month) < 7 else img_elem % IFA_N
            self.four = ''
            if report.block.lower() == 'wazirganj':
                if child_age > 23 and '1' in birth_spacing_prompt:
                    self.five = img_elem % SPACING_PROMPT_Y
                else:
                    self.five = img_elem % SPACING_PROMPT_N
            else:
                self.five = ''

        elif self.status == 'mother':
            if child_age != -1:
                self.month = child_age
            else:
                self.month = EMPTY_FIELD

            self.one = img_elem % C_ATTENDANCE_Y if 0 <= child_age <= 1 else img_elem % C_ATTENDANCE_N
            self.two = img_elem % C_WEIGHT_Y if child_age % 3 == 0 else img_elem % C_WEIGHT_N

            if child_age == 3:
                if met['child1_weight_calc'] or met['prev_child1_weight_calc']:
                    self.three = img_elem % CHILD_WEIGHT_Y
                else:
                    self.three = img_elem % CHILD_WEIGHT_N
            elif child_age == 6:
                if met['child1_register_calc'] or met['prev_child1_register_calc']:
                    self.three = img_elem % C_REGISTER_Y
                else:
                    self.three = img_elem % C_REGISTER_N
            elif child_age == 9:
                if met['child1_measles_calc'] or met['prev_child1_measles_calc']:
                    self.three = img_elem % MEASLEVACC_Y
                else:
                    self.three = img_elem % MEASLEVACC_N
            else:
                self.three = ''

            self.four = img_elem % EXCBREASTFED_Y if child_age == 6 else img_elem % EXCBREASTFED_N

            if child_age in [3, 6, 9]:
                if met['child1_suffer_diarrhea'] == '1':
                    self.five = img_elem % ORSZNTREAT_Y
                else:
                    self.five = img_elem % ORSZNTREAT_N
            elif child_age == [24, 36]:
                if met['interpret_grade_1'] == 'normal':
                    self.five = img_elem % GRADE_NORMAL_Y
                else:
                    self.five = img_elem % GRADE_NORMAL_N
            else:
                self.five = ''

        if report.block.lower() == 'atri':
            if child_age == 24:
                self.cash = '<span style="color: green;">Rs. 2000</span>'
            elif child_age == 36:
                self.cash = '<span style="color: green;">Rs. 3000</span>'
            elif met_one or met_two or met_three or met_four or met_five:
                self.cash = '<span style="color: green;">Rs. 250</span>'
            else:
                self.cash = '<span style="color: red;">Rs. 0</span>'

        elif report.block.lower() == 'wazirganj':
            if met_one or met_two or met_four or met_five:
                self.cash = '<span style="color: green;">Rs. 250</span>'
            else:
                self.cash = '<span style="color: red;">Rs. 0</span>'
