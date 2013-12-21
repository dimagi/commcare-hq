from datetime import datetime
from couchdbkit import ResourceNotFound

import dateutil.parser
from dateutil.relativedelta import relativedelta

from dimagi.utils.decorators.memoized import memoized
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser


class HOPECase(CommCareCase):
    '''
    Brute force extension with tons of computed fields in it
    '''
    registration_xmlns = 'http://bihar.commcarehq.org/pregnancy/registration'
    bp_xmlns = 'http://bihar.commcarehq.org/pregnancy/bp'
    delivery_xmlns = 'http://bihar.commcarehq.org/pregnancy/del'
    ebf_xmlns = 'http://bihar.commcarehq.org/pregnancy/ebf'
    pnc_xmlns = 'http://bihar.commcarehq.org/pregnancy/pnc'

    def forms_with_xmlns(self, xmlns):
        return sorted([form for form in self.get_forms() if form.xmlns == xmlns],
                      key=lambda form: form.received_on)

    #
    # Just a couple of helpers
    #

    @property
    @memoized
    def registration_form(self):
        forms = self.forms_with_xmlns(self.registration_xmlns)
        return forms[0] if forms else None

    @property
    @memoized
    def delivery_forms(self):
        return self.forms_with_xmlns(self.delivery_xmlns)

    @property
    @memoized
    def bp_forms(self):
        return self.forms_with_xmlns(self.bp_xmlns)

    @property
    @memoized
    def ebf_forms(self):
        return self.forms_with_xmlns(self.ebf_xmlns)

    @property
    @memoized
    def pnc_forms(self):
        return self.forms_with_xmlns(self.pnc_xmlns)

    def nth_dpt_opv_hb_doses_given(self, n):
        dpt = 'dpt_%d_date' % (n+1)
        opv = 'opv_%d_date' % (n+1)
        hb = 'hep_b_%d_date' % (n+1)

        return (
            bool(self.get_case_property(dpt)) and
            bool(self.get_case_property(opv)) and
            bool(self.get_case_property(hb))
        )

    def nth_ifa_issue_date(self, n):
        if len(self._HOPE_ifa_issue_dates) > n:
            return self._HOPE_ifa_issue_dates[n]
        else:
            return None

    @property
    def _HOPE_admission_date(self):
        if self.delivery_forms:
            return self.delivery_forms[0].get_form.get('adm_date')
        else:
            return None

    @property
    @memoized
    def user(self):
        user_id = self.user_id
        if user_id:
            try:
                return CommCareUser.get(user_id)
            except ResourceNotFound:
                return None
        else:
            return None

    #
    # Begin alphabetical rundown of custom properties requested
    #

    @property
    def _HOPE_all_anc_doses_given(self):
        anc_dose_dates = [self.get_case_property('anc_%d_date' % (n+1)) for n in range(0,4)]
        return len([date for date in anc_dose_dates if bool(date)]) >= 4

    @property
    def _HOPE_all_dpt1_opv1_hb1_doses_given(self):
        return self.nth_dpt_opv_hb_doses_given(0)

    @property
    def _HOPE_all_dpt2_opv2_hb2_doses_given(self):
        return self.nth_dpt_opv_hb_doses_given(1)

    @property
    def _HOPE_all_dpt3_opv3_hb3_doses_given(self):
        return self.nth_dpt_opv_hb_doses_given(2)

    @property
    def _HOPE_all_ifa_doses_given(self):
        return len(self._HOPE_ifa_issue_forms) >= 3

    @property
    def _HOPE_all_tt_doses_given(self):
        tt_dose_dates = [self.get_case_property('tt_%d_date' % (n+1)) for n in range(0, 4)]
        return len([date for date in tt_dose_dates if bool(date)]) >= 2

    @property
    def _HOPE_area_indicator(self):
        return self.registration_form.get_form.get('area_indicator') if self.registration_form else None

    @property
    def _HOPE_asha_id(self):
        user = self.user

        if user:
            return self.user.user_data.get('asha_id')
        else:
            return None

    @property
    def _HOPE_bcg_indicator(self):
        return bool(self.get_case_property('bcg_date'))

    @property
    def _HOPE_child_name(self):
        if self.type == 'cc_bihar_newborn':
            return self.name
        else:
            return None

    @property
    def _HOPE_delivery_nature(self):
        add = self.get_case_property('add')

        if not add:
            return None
        elif self.delivery_forms:
            return self.delivery_forms[-1].get_form.get('delivery_nature')
        else:
            return None

    @property
    def _HOPE_delivery_type(self):
        if not self.get_case_property('add'):
            return None
        else:
            birth_place = self.get_case_property('birth_place').strip()
            if birth_place == 'home':
                return 'home'
            elif birth_place == '':
                return None
            else:
                return 'institutional'

    @property
    def _HOPE_dpt_1_indicator(self):
        return bool(self.get_case_property('dpt_1_date'))


    @property
    def _HOPE_education(self):
        if self.registration_form:
            return self.registration_form.get_form.get('education')
        else:
            return None

    @property
    def _HOPE_existing_child_count(self):
        reg_form = self.registration_form

        num_girls = reg_form.get_form.get('num_girls', 0) if reg_form else 0
        num_boys = self.get_case_property('num_boys') or 0

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
    def _HOPE_ifa_issue_forms(self):
        ifa_issue_forms = []

        for form in self.bp_forms:
            ifa_tablets_issued = form.get_form.get('bp1', {}).get('ifa_tablets_issued')

            try:
                ifa_tablets_issued = int(ifa_tablets_issued)
            except (ValueError, TypeError):
                ifa_tablets_issued = 0

            if ifa_tablets_issued > 0:
                ifa_issue_forms.append(form)

        return ifa_issue_forms

    @property
    def _HOPE_ifa_issue_dates(self):
        return [form.received_on for form in self._HOPE_ifa_issue_forms]

    @property
    def _HOPE_ifa1_date(self):
        return self.nth_ifa_issue_date(0)

    @property
    def _HOPE_ifa2_date(self):
        return self.nth_ifa_issue_date(1)

    @property
    def _HOPE_ifa3_date(self):
        return self.nth_ifa_issue_date(2)

    @property
    def _HOPE_measles_dose_given(self):
        return bool(self.get_case_property('measles_date'))

    @property
    def _HOPE_number_of_visits(self):
        add = self.get_case_property('add')

        if not add:
            return 0

        return len([form for form in self.pnc_forms + self.ebf_forms
                    if (form.get_form.get("meta")['timeEnd'].date() - add).days <= 42])

    @property
    def _HOPE_opv_1_indicator(self):
        return bool(self.get_case_property('opv_1_date'))

    @property
    def _HOPE_registration_date(self):
        if self.delivery_forms:
            return  self.delivery_forms[-1].get_form.get('registration_date')
        else:
            return None

    @property
    def _HOPE_time_of_birth(self):
        if self.delivery_forms:
            return self.delivery_forms[0].get_form.get('time_of_birth')
        else:
            return None

    @property
    def _HOPE_tubal_ligation(self):
        if self.get_case_property('family_planning_type') == 'pptl_at_delivery':
            return True
        else:
            return False

