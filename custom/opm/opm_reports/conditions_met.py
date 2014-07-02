import datetime
from dimagi.utils.dates import months_between
from django.utils.translation import ugettext_lazy as _
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
            ('name', _("List of Beneficiary"), True),
            ('awc_name', _("AWC Name"), True),
            ('block_name', _("Block Name"), True),
            ('husband_name', _("Husband Name"), True),
            ('status', _("Current status"), True),
            ('preg_month', _('Pregnancy Month'), True),
            ('child_age', _("Child Age"), True),
            ('window', _("Window"), True),
            ('one', _("1"), True),
            ('two', _("2"), True),
            ('three', _("3"), True),
            ('four', _("4"), True),
            ('five', _("5"), True),
            ('cash', _("Payment Amount"), True),
            ('case_id', _('Case ID'), True),
            ('owner_id', _("Owner Id"), False),
            ('closed', _('Closed'), False)
        ],
        'wazirganj': [
            ('name', _("List of Beneficiary"), True),
            ('awc_name', _("AWC Name"), True),
            ('block_name', _("Block Name"), True),
            ('husband_name', _("Husband Name"), True),
            ('status', _("Current status"), True),
            ('preg_month', _('Pregnancy Month'), True),
            ('child_age', _("Child Age"), True),
            ('window', _("Window"), True),
            ('one', _("1"), True),
            ('two', _("2"), True),
            ('three', _("3"), True),
            ('four', _("4"), True),
            ('cash', _("Payment Amount"), True),
            ('case_id', _('Case ID'), True),
            ('owner_id', _("Owner Id"), False),
            ('closed', _('Closed'), False)
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
        def condition_image(image_y, image_n, condition):
            if condition is None:
                return ''
            elif condition is True:
                return img_elem % image_y
            elif condition is False:
                return img_elem % image_n

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
        case_property = lambda _property, default: get_property(case_obj, _property, default=default)

        self.case_id = get_property(case_obj, '_id', '')
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

        reporting_month = report.month
        reporting_year = report.year
        reporting_date = datetime.date(reporting_year, reporting_month + 1, 1) - datetime.timedelta(1)
        

        dod = get_property(case_obj, 'dod')
        edd = get_property(case_obj, 'edd')
        status = "unknown"
        preg_month = -1
        child_age = -1
        window = -1
        self.block_name = str(reporting_date)
        if not dod and not edd:
            raise InvalidRow
        if dod and dod != EMPTY_FIELD:
            try:
                dod_date = datetime.date(dod.year, dod.month, dod.day)
            except AttributeError:
                dod_date = None
                child_age = -1
            if dod_date and dod_date >= reporting_date:
                status = 'pregnant'
                preg_month = 9 - (dod_date - reporting_date).days / 30 # edge case
            elif dod_date and dod_date < reporting_date:
                status = 'mother'
                child_age = 1 + (reporting_date - dod_date).days / 30
        elif edd and edd != EMPTY_FIELD:
            try:
                edd_date = datetime.date(edd.year, edd.month, edd.day)
            except AttributeError:
                raise InvalidRow
            if edd_date and edd_date >= reporting_date:
                status = 'pregnant'
                preg_month = 9 - (edd_date - reporting_date).days / 30
            elif edd_date and edd_date < reporting_date: # edge case
                raise InvalidRow

        if status == 'pregnant' and (preg_month > 3 and preg_month < 10):
            window = (preg_month - 1) / 3
        elif status == 'pregnant' and (preg_month < 4 and preg_month > 9):
            raise InvalidRow
        elif status == 'mother' and (child_age > 0 and child_age < 37):
            window = (child_age - 1) / 3 + 1
        elif status == 'mother' and (child_age < 1 and child_age > 36):
            raise InvalidRow
        else:
            raise InvalidRow

        if status == "unknown" or window == -1 or (child_age == -1 and preg_month == -1):
            raise InvalidRow

        self.status = status
        self.child_age = child_age
        self.preg_month = preg_month
        self.window = window

        met_one = False
        met_two = False
        met_three = False
        met_four = False
        met_five = False
        # preg_month = get_property(case_obj, 'pregnancy_month', 0) or 0
        vhnd_attendance = {
            4: case_property('attendance_vhnd_1', 0),
            5: case_property('attendance_vhnd_2', 0),
            6: case_property('attendance_vhnd_3', 0),
            7: case_property('month_7_attended', 0),
            8: case_property('month_7_attended', 0)
        }
        if self.status == 'pregnant':
            met_one, met_two, met_three = None, None, None
            self.child_age = EMPTY_FIELD
            if self.preg_month != 9:
                met_one = vhnd_attendance[self.preg_month] == '1'
            if self.preg_month == 6:
                met_two = '1' in [case_property('weight_tri_1', 0), case_property('prev_weight_tri_1', 0)]
                met_three = case_property('ifa_tri1', 0) == '1'
            if self.preg_month == 9:
                met_two = '1' in [case_property('weight_tri_1', 0), case_property('prev_weight_tri_1', 0)]         
            
            self.one = condition_image(M_ATTENDANCE_Y, M_ATTENDANCE_N, met_one)
            self.two = condition_image(M_WEIGHT_Y, M_WEIGHT_N, met_two)
            self.three = condition_image(IFA_Y, IFA_N, met_three)
            self.four = ''

        if self.status == 'mother':
            self.preg_month = EMPTY_FIELD
            met_one, met_two, met_three = None, None, None
            self.one, self.two, self.three, self.four, self.five = '','','','',''
            if self.child_age != 1:
                met_one = '1' in [met['child1_vhndattend_calc'], met['prev_child1_vhndattend_calc'], met['child1_attendance_vhnd']]
                self.one = condition_image(C_ATTENDANCE_Y, C_ATTENDANCE_N, met_one)
            if self.child_age % 3 == 0:
                met_two = '1' in [met['child1_growthmon_calc'], met['prev_child1_growthmon_calc']]
                met_three = '1' in [met['child1_ors_calc'], met['prev_child1_ors_calc']]
                self.two = condition_image(C_WEIGHT_Y, C_WEIGHT_N, met_two)
                self.three = condition_image(ORSZNTREAT_Y, ORSZNTREAT_N, met_three)
            if self.child_age == 3:
                met_four = 'received' in [met['child1_weight_calc'], met['prev_child1_weight_calc']]
                met_five = 'received' in [met['child1_excl_breastfeed_calc'], met['prev_child1_excl_breastfeed_calc']]
                self.four = condition_image(CHILD_WEIGHT_Y, CHILD_WEIGHT_N, met_four)
                self.five = condition_image(EXCBREASTFED_Y, EXCBREASTFED_N, met_five)
            if self.child_age == 6:
                met_four = 'received' in [met['child1_register_calc'] or met['prev_child1_register_calc']]
                met_five = 'received' in [met['child1_excl_breastfeed_calc'], met['prev_child1_excl_breastfeed_calc']]
                self.four = condition_image(C_REGISTER_Y, C_REGISTER_N, met_four)
                self.five = condition_image(EXCBREASTFED_Y, EXCBREASTFED_N, met_five)
            if self.child_age == 12:
                met_four = 'received' in [met['child1_measles_calc'] or met['prev_child1_measles_calc']]
                self.four = condition_image(MEASLEVACC_Y, MEASLEVACC_N, met_four)

        self.name = get_property(case_obj, 'name')
        # self.awc_name = get_property(case_obj, 'awc_name')
        # self.husband_name = get_property(case_obj, 'husband_name')
        self.awc_name = str(dod)
        self.husband_name = str(edd)

        if self.status == 'pregnant':
            if report.block.lower() == 'wazirganj':
                if child_age > 23 and '1' in birth_spacing_prompt:
                    self.five = img_elem % SPACING_PROMPT_Y
                else:
                    self.five = img_elem % SPACING_PROMPT_N
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
