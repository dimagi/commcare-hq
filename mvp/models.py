from couchdbkit.ext.django.schema import StringProperty, IntegerProperty, ListProperty, SetProperty, DocumentSchema
import datetime
from couchdbkit.schema.properties import LazyDict
import dateutil
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormDataInCaseIndicatorDefinition,\
    PopulateRelatedCasesWithIndicatorDefinitionMixin, CaseDataInFormIndicatorDefinition
from couchforms.models import XFormInstance

class MVP(object):
    NAMESPACE = "mvp_indicators"
    DOMAINS = ["mvp-sauri", "mvp-potou"]

CLASS_PATH = "mvp.models"

class MVPCannotFetchCaseError(Exception):
    pass


class MVPRelatedCaseMixin(DocumentSchema):
    related_case_type = StringProperty()

    def get_related_cases(self, original_case):
        if hasattr(original_case, 'household_head_health_id'):
            household_id = original_case.household_head_health_id
        elif hasattr(original_case, 'household_head_id'):
            household_id = original_case.household_head_id
        else:
            raise MVPCannotFetchCaseError("Cannot fetch appropriate case from %s." % original_case.get_id)
        key = [original_case.domain, self.related_case_type, household_id]
        cases = CommCareCase.view("mvp/cases_by_household",
            reduce=False,
            include_docs=True,
            startkey=key,
            endkey=key+[{}]
        ).all()
        return cases


class MVPRelatedCaseDataInFormIndicatorDefinition(CaseDataInFormIndicatorDefinition, MVPRelatedCaseMixin):
    _class_path = CLASS_PATH
    _returns_multiple = True

    def get_value(self, doc):
        values = list()
        form_data = doc.get_form
        related_case_id = form_data.get('case', {}).get('@case_id')
        if related_case_id:
            case = CommCareCase.get(related_case_id)
            if isinstance(case, CommCareCase):
                related_cases = self.get_related_cases(case)
                for rc in related_cases:
                    if hasattr(rc, str(self.case_property)):
                        values.append(dict(
                            case_id=rc.get_id,
                            case_opened=rc.opened_on,
                            case_closed=rc.closed_on,
                            value=getattr(rc, str(self.case_property))
                        ))
        return values


class MVPRelatedCaseDataInCaseIndicatorDefinition(CaseIndicatorDefinition, MVPRelatedCaseMixin):
    related_case_property = StringProperty()

    _class_path = CLASS_PATH
    _returns_multiple = True

    def get_value(self, case):
        values = list()
        related_cases = self.get_related_cases(case)
        for rc in related_cases:
            if hasattr(rc, str(self.related_case_property)):
                values.append(dict(
                    case_id=rc.get_id,
                    case_opened=rc.opened_on,
                    case_closed=rc.closed_on,
                    value=getattr(rc, str(self.related_case_property))
                ))
        return values
