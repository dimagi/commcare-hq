from __future__ import absolute_import
from __future__ import unicode_literals
from couchdbkit import ResourceNotFound

from memoized import memoized
from casexml.apps.case.models import CommCareCase
from corehq.apps.users.models import CommCareUser
from custom.hope.const import MOTHER_OTHER_PROPERTIES, CHILD_OTHER_PROPERTIES, CHILD_EVENTS_ATTRIBUTES, MOTHER_EVENTS_ATTRIBUTES
from six.moves import range

CC_BIHAR_NEWBORN = 'cc_bihar_newborn'

CC_BIHAR_PREGNANCY = 'cc_bihar_pregnancy'


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
            return self.delivery_forms[0].form.get('adm_date')
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

    def bool_to_yesno(self, value):
        if value is None:
            return None
        elif value:
            return 'yes'
        else:
            return 'no'

    @property
    @memoized
    def parent(self):
        for index in self.indices:
            if index.identifier == 'mother_id':
                return HOPECase.get(index.referenced_id)
        return None

    @classmethod
    def get_event(self, event_cd, event_name, event_value):
        return {
            "event_cd": event_cd,
            "name": event_name,
            "value": event_value
        }

    def get_other_properties(self, properties_list):
        properties = { }
        for property in properties_list:
            if hasattr(self, property[1]) and getattr(self, property[1]) != None:
                properties.update({property[0]: getattr(self, property[1])})
        return properties

    def get_events_attributes(self, events_attributes_list):
        events_attributes = [ ]
        for event in events_attributes_list:

            if hasattr(self, event[2]) and getattr(self, event[2]) != None:
                events_attributes.append(self.get_event(event[0], event[1], getattr(self, event[2]) ))
        return events_attributes

    #
    # Retrieving basic properties and events attributes based on case type
    #

    @property
    def other_properties(self):
        other_properties = { }
        if self.type == CC_BIHAR_PREGNANCY:
            other_properties = self._HOPE_mother_other_properties
        if self.type == CC_BIHAR_NEWBORN:
            other_properties = self._HOPE_child_other_properties
        return other_properties

    @property
    def events_attributes(self):
        events_attributes = [ ]
        if self.type == CC_BIHAR_PREGNANCY:
            events_attributes = self._HOPE_mother_events_attributes
        if self.type == CC_BIHAR_NEWBORN:
            events_attributes = self._HOPE_child_events_attributes
        return events_attributes

    @property
    def _HOPE_mother_other_properties(self):
        return self.get_other_properties(MOTHER_OTHER_PROPERTIES)

    @property
    def _HOPE_child_other_properties(self):
        return self.get_other_properties(CHILD_OTHER_PROPERTIES)

    @property
    def _HOPE_mother_events_attributes(self):
        return self.get_events_attributes(MOTHER_EVENTS_ATTRIBUTES)

    @property
    def _HOPE_child_events_attributes(self):
        return self.get_events_attributes(CHILD_EVENTS_ATTRIBUTES)

    #
    # Begin mother other properties
    #

    @property
    def _HOPE_mother_mother_name(self):
        return self.get_case_property('mother_name')

    @property
    def _HOPE_mother_husband_name(self):
        return self.get_case_property('husband_name')

    @property
    def _HOPE_mother_program_cd(self):
        program_code = None
        if self._HOPE_area_indicator == 'r' and self._HOPE_delivery_type == 'institutional' and self._HOPE_delivery_nature != 'caesarian' and self._HOPE_all_anc_doses_given:
            program_code = 'JBSYINSRRL'

        if self._HOPE_area_indicator == 'r' and self._HOPE_delivery_type == 'institutional' and self._HOPE_delivery_nature != 'caesarian' and not self._HOPE_all_anc_doses_given:
            program_code = 'JBSYINSRRLDEL'

        if self._HOPE_delivery_type == 'home' and self._HOPE_delivery_nature != 'caesarian':
            program_code = 'JBSYHM'

        if self._HOPE_area_indicator == 'u' and self._HOPE_delivery_type == 'institutional' and self._HOPE_delivery_nature != 'caesarian' and self._HOPE_all_anc_doses_given:
            program_code = 'JBSYINSURB'

        if self._HOPE_area_indicator == 'r' and self._HOPE_delivery_type == 'institutional' and self._HOPE_delivery_nature != 'caesarian' and not self._HOPE_all_anc_doses_given:
            program_code = 'JBSYINSURBDEL'

        if self._HOPE_delivery_type == 'institutional' and self._HOPE_delivery_nature == 'caesarian':
            program_code = 'JBSYCEC'

        return program_code

    @property
    def _HOPE_mother_bank_account_number(self):
        return self.get_case_property('bank_account_number')

    @property
    def _HOPE_mother_bank_id(self):
        return self.get_case_property('bank_id')

    @property
    def _HOPE_mother_bank_branch_id(self):
        return self.get_case_property('bank_branch_id')

    @property
    def _HOPE_mother_ifsc_code(self):
        return self.get_case_property('ifsc_code')

    @property
    def _HOPE_mother_full_mcts_id(self):
        return self.get_case_property('full_mcts_id')

    #
    # Begin child other properties
    #

    @property
    def _HOPE_child_parent_mother_name(self):
        if self.parent:
            return self.parent.get_case_property('mother_name')
        return None

    @property
    def _HOPE_child_parent_husband_name(self):
        if self.parent:
            return self.parent.get_case_property('husband_name')
        return None

    @property
    def _HOPE_child_parent_bank_account_number(self):
        if self.parent:
            return self.parent.get_case_property('bank_account_number')
        return None

    @property
    def _HOPE_child_parent_bank_id(self):
        if self.parent:
            return self.parent.get_case_property('bank_id')
        return None

    @property
    def _HOPE_child_parent_bank_branch_id(self):
        if self.parent:
            return self.parent.get_case_property('bank_branch_id')
        return None

    @property
    def _HOPE_child_parent_ifsc_code(self):
        if self.parent:
            return self.parent.get_case_property('ifsc_code')
        return None

    @property
    def _HOPE_child_parent_full_mcts_id(self):
        if self.parent:
            return self.parent.get_case_property('full_mcts_id')
        return None

    @property
    def _HOPE_child_full_child_mcts_id(self):
        return self.get_case_property('full_child_mcts_id')

    @property
    def _HOPE_agency_cd(self):
        user = self.user

        if user:
            return self.user.user_data.get('agency_cd')
        else:
            return None

    #
    # Begin AHSA properties
    #

    @property
    def _HOPE_asha_id(self):
        user = self.user

        if user:
            return self.user.user_data.get('asha_id')
        else:
            return None

    @property
    def _HOPE_asha_bank_account_number(self):
        user = self.user

        if user:
            return self.user.user_data.get('asha_bank_account_number')
        else:
            return None

    @property
    def _HOPE_asha_bank_id(self):
        user = self.user

        if user:
            return self.user.user_data.get('asha_bank_id')
        else:
            return None

    @property
    def _HOPE_asha_ifsc_code(self):
        user = self.user

        if user:
            return self.user.user_data.get('asha_ifsc_code')
        else:
            return None

    @property
    def _HOPE_asha_bank_branch_id(self):
        user = self.user

        if user:
            return self.user.user_data.get('asha_bank_branch_id')
        else:
            return None

    #
    # Begin mother event_attributes
    #

    @property
    def _HOPE_mother_anc_1_date(self):
        return self.get_case_property('anc_1_date')

    @property
    def _HOPE_mother_anc_2_date(self):
        return self.get_case_property('anc_2_date')

    @property
    def _HOPE_mother_anc_3_date(self):
        return self.get_case_property('anc_3_date')

    @property
    def _HOPE_mother_anc_4_date(self):
        return self.get_case_property('anc_4_date')

    @property
    def _HOPE_mother_all_anc_doses_given(self):
        anc_dose_dates = [self.get_case_property('anc_%d_date' % (n+1)) for n in range(0, 4)]
        return self.bool_to_yesno(len([date for date in anc_dose_dates if bool(date)]) >= 4)

    @property
    def _HOPE_mother_patient_reg_num(self):
        return self.get_case_property('patient_reg_num')

    @property
    def _HOPE_mother_registration_date(self):
        if self.delivery_forms:
            return self.delivery_forms[-1].form.get('registration_date')
        else:
            return None

    @property
    def _HOPE_mother_existing_child_count(self):
        reg_form = self.registration_form

        num_girls = reg_form.form.get('num_girls', 0) if reg_form else 0
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
    def _HOPE_mother_age(self):
        return self.get_case_property('age')

    @property
    def _HOPE_mother_bpl_indicator(self):
        return bool(self.get_case_property('bpl'))

    @property
    def _HOPE_mother_delivery_date(self):
        return self.get_case_property('add')

    @property
    def _HOPE_mother_time_of_birth(self):
        if self.delivery_forms:
            return self.delivery_forms[0].form.get('time_of_birth')
        else:
            return None

    @property
    def _HOPE_mother_tubal_ligation(self):
        if self.get_case_property('family_planning_type') == 'pptl_at_delivery':
            return self.bool_to_yesno(True)
        else:
            return self.bool_to_yesno(False)

    @property
    def _HOPE_mother_area_indicator(self):
        return self._HOPE_area_indicator

    @property
    def _HOPE_mother_ifa1_date(self):
        return self.nth_ifa_issue_date(0)

    @property
    def _HOPE_mother_ifa2_date(self):
        return self.nth_ifa_issue_date(1)

    @property
    def _HOPE_mother_ifa3_date(self):
        return self.nth_ifa_issue_date(2)

    @property
    def _HOPE_mother_all_ifa_doses_given(self):
        return self.bool_to_yesno(len(self._HOPE_ifa_issue_forms) >= 3)

    @property
    def _HOPE_mother_tt_1_date(self):
        return self.get_case_property('tt_1_date')

    @property
    def _HOPE_mother_tt_2_date(self):
        return self.get_case_property('tt_2_date')

    @property
    def _HOPE_mother_all_tt_doses_given(self):
        tt_dose_dates = [self.get_case_property('tt_%d_date' % (n+1)) for n in range(0, 4)]
        return self.bool_to_yesno(len([date for date in tt_dose_dates if bool(date)]) >= 2)

    #
    # Begin child event_attributes
    #

    @property
    def _HOPE_child_child_name(self):
        return self.get_case_property('child_name')

    @property
    def _HOPE_child_mother_name(self):
        if self.parent:
            return self.parent.get_case_property('mother_name')
        return None

    @property
    def _HOPE_child_mother_husband_name(self):
        if self.parent:
            return self.parent.get_case_property('husband_name')
        return None

    @property
    def _HOPE_child_number_of_visits(self):
        if self.parent:
            add = self.parent.get_case_property('add')

            if not add:
                return 0

            return len([form for form in self.parent.pnc_forms + self.parent.ebf_forms
                        if (form.form.get("meta")['timeEnd'].date() - add).days <= 42])
        else:
            return 0

    @property
    def _HOPE_child_bcg_indicator(self):
        return bool(self.get_case_property('bcg_date'))

    @property
    def _HOPE_child_opv_1_indicator(self):
        return bool(self.get_case_property('opv_1_date'))

    @property
    def _HOPE_child_dpt_1_indicator(self):
        return bool(self.get_case_property('dpt_1_date'))

    @property
    def _HOPE_child_delivery_type(self):
        if self.parent:
            return self.parent._HOPE_delivery_type
        return None

    @property
    def _HOPE_child_dpt_1_date(self):
        return self.get_case_property('dpt_1_date')

    @property
    def _HOPE_child_opv_1_date(self):
        return self.get_case_property('opv_1_date')

    @property
    def _HOPE_child_hep_b_1_date(self):
        return self.get_case_property('hep_b_1_date')

    @property
    def _HOPE_child_dpt_2_date(self):
        return self.get_case_property('dpt_2_date')

    @property
    def _HOPE_child_opv_2_date(self):
        return self.get_case_property('opv_2_date')

    @property
    def _HOPE_child_hep_b_2_date(self):
        return self.get_case_property('hep_b_2_date')

    @property
    def _HOPE_child_dpt_3_date(self):
        return self.get_case_property('dpt_3_date')

    @property
    def _HOPE_child_opv_3_date(self):
        return self.get_case_property('opv_3_date')

    @property
    def _HOPE_child_hep_b_3_date(self):
        return self.get_case_property('hep_b_3_date')

    @property
    def _HOPE_child_measles_date(self):
        return self.get_case_property('measles_date')

    @property
    def _HOPE_child_dob(self):
        return self.get_case_property('dob')

    @property
    def _HOPE_child_all_dpt1_opv1_hb1_doses_given(self):
        return self.bool_to_yesno(self.nth_dpt_opv_hb_doses_given(0))

    @property
    def _HOPE_child_all_dpt2_opv2_hb2_doses_given(self):
        return self.bool_to_yesno(self.nth_dpt_opv_hb_doses_given(1))

    @property
    def _HOPE_child_all_dpt3_opv3_hb3_doses_given(self):
        return self.bool_to_yesno(self.nth_dpt_opv_hb_doses_given(2))

    @property
    def _HOPE_child_measles_dose_given(self):
        return self.bool_to_yesno(bool(self.get_case_property('measles_date')))

    #
    # Custom help properties for both case types
    #

    @property
    def _HOPE_area_indicator(self):
        return self.registration_form.form.get('area_indicator') if self.registration_form else None

    @property
    def _HOPE_delivery_nature(self):
        add = self.get_case_property('add')

        if not add:
            return None
        elif self.delivery_forms:
            return self.delivery_forms[-1].form.get('delivery_nature')
        else:
            return None

    @property
    def _HOPE_delivery_type(self):
        if not self.get_case_property('add'):
            return None
        else:
            try:
                birth_place = self.get_case_property('birth_place').strip()
                if birth_place == 'home':
                    return 'home'
                elif birth_place == '':
                    return None
                else:
                    return 'institutional'
            except AttributeError:
                return None

    @property
    def _HOPE_ifa_issue_forms(self):
        ifa_issue_forms = []

        for form in self.bp_forms:
            ifa_tablets_issued = form.form.get('bp1', {}).get('ifa_tablets_issued')

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



