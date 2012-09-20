from couchdbkit.ext.django.schema import StringProperty, IntegerProperty, ListProperty, SetProperty, DocumentSchema
import datetime
from couchdbkit.schema.properties import LazyDict
import dateutil
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormDataInCaseIndicatorDefinition,\
    PopulateRelatedCasesWithIndicatorDefinitionMixin
from couchforms.models import XFormInstance

class MVP(object):
    NAMESPACE = "mvp_indicators"
    DOMAINS = ["mvp-sauri"]

CLASS_PATH = "mvp.models"

class MVPCaseRelatedToHouseholdIndicatorDefinition(CaseIndicatorDefinition,
    PopulateRelatedCasesWithIndicatorDefinitionMixin):

    _class_path = CLASS_PATH

    def set_related_cases(self, case):
        get_household_id_attr = 'household_head_id' if hasattr(case, 'household_head_id') \
                                                    else 'household_head_health_id'
        household_id = getattr(case, get_household_id_attr)
        related_cases = list()
        for case_type in self.related_case_types:
            key = [case.domain, case_type, household_id]
            related_cases.extend(CommCareCase.view("mvp/cases_by_household",
                reduce=False,
                include_docs=True,
                startkey=key,
                endkey=key+[{}]
            ).all())
        print "RELATED CASES", [c.get_id for c in related_cases]
        self._related_cases = related_cases

    def get_clean_value(self, doc):
        value = super(MVPCaseRelatedToHouseholdIndicatorDefinition, self).get_clean_value(doc)
        self.set_related_cases(doc)
        self.populate_with_value(value)
        return value


class MVPLessThanAgeIndicatorDefinition(MVPCaseRelatedToHouseholdIndicatorDefinition):
        """
            Create a case-based indicator for the MVP child case that sets
            under_five = True if the child is under 5 _years_ of age.
        """
        age_in_months = IntegerProperty()

        def get_value(self, doc):
            if hasattr(doc, 'age') and hasattr(doc, 'months_or_years'):
                multiplier = 12 if (doc.months_or_years == 'years') else 1
                age_in_months = int(doc.age) * int(multiplier)
            elif hasattr(doc, 'dob'):
                age_in_months = self.age_from_dob(doc)
            else:
                raise ValueError("Cannot grab the age from this case. No 'age' or 'dob' available.")
            return int(age_in_months) < int(self.age_in_months)

        def age_from_dob(self, doc):
            dob = doc.dob_calc
            today = doc.modified_on.date()
            if isinstance(dob, str):
                dob = dateutil.parser.parse(dob)
            td = today-dob
            return int(round((float(td.days)/365)*12))


class MVPPregnantWomanInHouseholdIndicatorDefinition(MVPCaseRelatedToHouseholdIndicatorDefinition):

    def get_value(self, doc):
        #todo finish this
        currently_pregnant = bool(doc.closed == 'no')
        pregnancy_info = dict(currently_pregnant=currently_pregnant)
        if not currently_pregnant:
            pass


        return False


class MVPDangerSignIndicatorDefinition(FormDataInCaseIndicatorDefinition):
    """
        Case-based form data indicator for keeping track of danger signs.
    """

    _class_path = CLASS_PATH

    def get_value_for_form(self, form_data):
        danger_keys = ["patient_available.immediate_danger_sign",
                       "patient_available.emergency_danger_sign",
                       "curr_danger_type"]
        return list(self.get_signs_for_keys(form_data, danger_keys))

    def get_signs_for_keys(self, form_data, keys):
        all_signs = list()
        for key in keys:
            signs = self.get_from_form(form_data, key.split('.')).strip()
            signs = [s for s in signs.split(' ') if s]
            all_signs.extend(signs)
        return set(all_signs)



