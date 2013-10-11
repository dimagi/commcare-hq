from datetime import datetime

import dateutil.parser
from dateutil.relativedelta import relativedelta

from casexml.apps.case.models import CommCareCase

class HOPECase(CommCareCase):
    '''
    Brute force extension with tons of computed fields in it
    '''
    registration_xmlns = 'http://bihar.commcarehq.org/pregnancy/registration'
    bp_xmlns = 'http://bihar.commcarehq.org/pregnancy/bp'
    delivery_xmlns = 'http://bihar.commcarehq.org/pregnancy/del'

    def forms_with_xmlns(self, xmlns):
        return sorted([form for form in self.get_forms() if form.xmlns == xmlns],
                      key=lambda form: form.received_on)

    #
    # Just a couple of helpers
    #

    def nth_dpt_opv_hb_doses_given(self, n):
        dpt = 'dpt_%d_date' % (n+1)
        opv = 'opv_%d_date' % (n+1)
        hb = 'hb_%d_date' % (n+1)

        return bool(self.properties().get(dpt)) and bool(self.properties().get(opv)) and bool(self.properties().get(hb))

    def nth_ifa_issue_date(self, n):
        if len(self.ifa_issue_dates) > n:
            return self.ifa_issue_dates[n]
        else:
            return None

    #
    # Begin alphabetical rundown of custom properties requested
    #

    @property
    def admission_date(self):
        forms = self.forms_with_xmlns(self.delivery_xmlns)
        if forms:
            return forms[0].get_form.get('adm_date')
        else:
            return None

    @property
    def age_of_beneficiary(self):
        mother_dob = self.properties().get('mother_dob')
        if mother_dob:
            mother_dob = dateutil.parser.parse(mother_dob)
            return relativedelta(datetime.now(), mother_dob).years
        else:
            return None

    @property
    def all_anc_doses_given(self):
        anc_dose_dates = [self.properties().get('anc_%d_date' % (n+1)) for n in range(0,4)]
        return len([date for date in anc_dose_dates if bool(date)]) >= 4

    @property
    def all_dpt1_opv1_hb1_doses_given(self):
        return self.nth_dpt_opv_hb_doses_given(0)

    @property
    def all_dpt2_opv2_hb2_doses_given(self):
        return self.nth_dpt_opv_hb_doses_given(1)

    @property
    def all_dpt3_opv3_hb3_doses_given(self):
        return self.nth_dpt_opv_hb_doses_given(2)

    @property
    def all_ifa_doses_given(self):
        return len(self.ifa_issue_forms) >= 3

    @property
    def all_tt_doses_given(self):
        tt_dose_dates = [self.properties().get('tt_%d_date' % (n+1)) for n in range(0, 4)]
        return len([date for date in tt_dose_dates if bool(date)]) >= 2

    @property
    def bpl_indicator(self):
        forms = self.forms_with_xmlns(self.registration_xmlns)
        if forms:
            return forms[0].get_form.get('bpl_indicator')
        else:
            return None

    @property
    def child_age(self):
        dob = self.properties().get('dob')
        if dob:
            dob = dateutil.parser.parse(dob)
            age = relativedelta(datetime.now(), dob)
            return age.years*12 + age.months
        else:
            return None


    @property
    def delivery_type(self):
        return 'home' if self.properties().get('birth_place') == 'home' else 'institution'

    @property
    def discharge_date(self):
        forms = self.forms_with_xmlns(self.delivery_xmlns)
        if forms:
            return forms[0].get_form.get('dis_date')
        else:
            return None

    @property
    def education(self):
        forms = self.forms_with_xmlns(self.registration_xmlns)
        if forms:
            return forms[0].get_form.get('education')
        else:
            return None

    @property
    def existing_child_count(self):
        forms = self.forms_with_xmlns(self.registration_xmlns)
        num_girls = forms[0].get_form.get('num_girls', 0) if forms else 0
        num_boys = self.properties().get('num_boys', 0)

        # The form fields are strings; the coercion to int is deliberately
        # isolated here so unrelated errors do not get caught
        try:
            num_girls = int(num_girls)
        except ValueError:
            num_girls = 0

        try:
            num_boys = int(num_boys)
        except ValueError:
            num_boys = 0

        return num_girls + num_boys

    @property
    def ifa_issue_forms(self):
        return [form for form in self.forms_with_xmlns(self.bp_xmlns)
                if form.get_form.get('if_tablet_issued')]

    @property
    def ifa_issue_date(self):
        return [form.date_modified for form in self.ifa_issue_forms]

    @property
    def ifa1_date(self):
        return self.nth_ifa_issue_date(0)

    @property
    def ifa2_date(self):
        return self.nth_ifa_issue_date(1)

    @property
    def ifa3_date(self):
        return self.nth_ifa_issue_date(2)

    @property
    def measles_dose_given(self):
        return bool(self.properties().get('measles_date'))

    @property
    def num_visits(self):
        visit_dates = [self.properties().get('visit_%d_date') % (n+1) for n in range(0,7)]
        return len([date for date in visit_dates if date])

    @property
    def patient_reg_num(self):
        forms = self.forms_with_xmlns(self.delivery_xmlns)
        if forms:
            return forms[0].get_form.get('patient_reg_form')
        else:
            return None

    @property
    def registration_date(self):
        forms = self.forms_with_xmlns(self.registration_xmlns)

        if not forms:
            return ''
        else:
            reg_form = forms[0]
            if reg_form.get_form.get('jsy_beneficiary', False):
                return self.get_server_modified_date()
            else:
                return ''

    @property
    def time_of_birth(self):
        forms = self.forms_with_xmlns(self.delivery_xmlns)
        if forms:
            return forms[0].get_form.get('time_of_birth')
        else:
            return None

    @property
    def tubal_ligation(self):
        if self.properties().get('family_planning_type') == 'pptl_at_delivery':
            return True
        else:
            return False

