from couchdbkit.ext.django.schema import StringProperty, IntegerProperty, ListProperty, SetProperty, DocumentSchema, Document
import datetime
from couchdbkit.schema.properties import LazyDict
import dateutil
from casexml.apps.case.models import CommCareCase
from corehq.apps.indicators.models import CaseIndicatorDefinition, FormDataInCaseIndicatorDefinition,\
    PopulateRelatedCasesWithIndicatorDefinitionMixin, CaseDataInFormIndicatorDefinition
from couchforms.models import XFormInstance
from dimagi.utils.couch.database import get_db

class MVP(object):
    NAMESPACE = "mvp_indicators"
    DOMAINS = ["mvp-sauri", "mvp-potou"]
    CHILD_VISIT_QUESTION_IDS = dict(
        immediate_danger_sign={
            'mvp-sauri': 'patient_available.immediate_danger_sign',
            'mvp-potou': 'patient_available.immediate_danger_sign'
        },
        rdt_result={
            'mvp-sauri': 'patient_available.referral_follow_on.rdt_result',
            'mvp-potou': 'patient_available.referral_follow_on.rdt_result'
        },
        fever_medication={
            'mvp-sauri': 'patient_available.medication_type',
            'mvp-potou': 'patient_available.fever_medication'
        },
        diarrhea_medication={
            'mvp-sauri': 'patient_available.medication_type',
            'mvp-potou': 'patient_available.diarrhea_medication'
        },
        referral_type={
            'mvp-sauri': 'group_referral_dangersign.referral_type',
            'mvp-potou': 'patient_available.referral_type'
        },
        muac={
            'mvp-sauri': 'patient_available.muac',
            'mvp-potou': 'patient_available.muac'
        }
    )
    PREGNANCY_VISIT_QUESTION_IDS = dict(
        prev_num_anc={
            'mvp-sauri': 'group_counseling.prev_num_anc',
            'mvp-potou': 'prev_cur_num_anc'
        },
        num_anc={
            'mvp-sauri': 'group_counseling.num_anc',
            'mvp-potou': 'group_counseling.num_anc',
        },
        last_anc_date={
            'mvp-sauri': 'group_counseling.last_anc_date',
        },
        last_anc_weeks={
            'mvp-potou': 'last_anc_weeks'
        }
    )
    HOUSEHOLD_VISIT_QUESTION_IDS = dict(
        num_using_fp={
            'mvp-sauri': 'num_using_fp',
            'mvp-potou': 'num_using_fp'
        },
        num_ec={
            'mvp-sauri': 'num_ec',
            'mvp-potou': 'num_ec'
        }
    )
    VISIT_FORMS = dict(
        pregnancy_visit='http://openrosa.org/formdesigner/185A7E63-0ECD-4D9A-8357-6FD770B6F065',
        child_visit='http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A',
        household_visit='http://openrosa.org/formdesigner/266AD1A0-9EAE-483E-B4B2-4E85D6CA8D4B'
    )

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


#class MVPUnder5IndicatorHandler(IndicatorHandler):
#    couch_prefix = StringProperty()
#
#    def get_value(self, domain, startdate, enddate, user_id=None):
#        if isinstance(startdate, datetime.datetime):
#            startdate = startdate.isoformat()
#        if isinstance(enddate, datetime.datetime):
#            enddate = enddate.isoformat()
#        couch_key = ["user", domain, user_id, self.couch_prefix]
#        data = get_db().view('mvp/under5_child_health',
#            reduce=True,
#            startkey=couch_key+[startdate],
#            endkey=couch_key+[enddate]
#        ).first()
#        if not data:
#            return 0
#        return data.get('value', 0)