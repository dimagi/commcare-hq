from django.core.management.base import LabelCommand
from corehq.apps.indicators.models import CaseDataInFormIndicatorDefinition, FormDataAliasIndicatorDefinition, \
    FormDataInCaseIndicatorDefinition, DocumentIndicatorDefinition
from mvp.models import MVP

CHILD_VISIT_QUESTION_IDS = dict(
    immediate_danger_sign={
        'mvp-sauri': 'patient_available.immediate_danger_sign',
        'mvp-potou': 'patient_available.immediate_danger_sign',
    },
    emergency_danger_sign={
        'mvp-sauri': 'patient_available.emergency_danger_sign',
        'mvp-potou': 'patient_available.emergency_danger_sign',
    },
    visit_hospital={
        'mvp-sauri': 'visit_hospital',
        'mvp-potou': 'visit_hospital',
    },
    rdt_result={
        'mvp-sauri': 'patient_available.referral_follow_on.rdt_result',
        'mvp-potou': 'patient_available.referral_follow_on.rdt_result',
    },
    fever_medication={
        'mvp-sauri': 'patient_available.fever_medication',
        'mvp-potou': 'patient_available.medication_type',
    },
    diarrhea_medication={
        'mvp-sauri': 'patient_available.diarrhea_medication',
        'mvp-potou': 'patient_available.medication_type',
    },
    referral_type={
        'mvp-sauri': 'patient_available.referral_type',
        'mvp-potou': 'patient_available.referral_type',
    },
    muac={
        'mvp-sauri': 'patient_available.muac',
        'mvp-potou': 'patient_available.muac',
    },
    exclusive_breastfeeding={
        'mvp-sauri': 'group_counseling.exclusive_breastfeeding',
        'mvp-potou': 'exclusive_breastfeeding',
    }
)

PREGNANCY_VISIT_QUESTION_IDS = dict(
    immediate_danger_sign={
        'mvp-sauri': 'patient_available.immediate_danger_sign',
        'mvp-potou': 'immediate_danger_sign',
        },
    emergency_danger_sign={
        'mvp-sauri': 'emergency_danger_sign',
        'mvp-potou': 'emergency_danger_sign',
        },
    prev_num_anc={
        'mvp-sauri': 'group_counseling.prev_num_anc',
        'mvp-potou': 'prev_num_anc',
    },
    num_anc={
        'mvp-sauri': 'group_counseling.num_anc',
        'mvp-potou': 'group_counseling.num_anc',
        },
    last_anc_date={
        'mvp-sauri': 'group_counseling.last_anc_date',
        },
    last_anc_weeks={
        'mvp-potou': 'group_counseling.last_anc_weeks',
    },
    referral_type={
        'mvp-sauri': 'group_referral_dangersign.referral_type',
        'mvp-potou': 'group_referral_dangersign.referral_type',
    }
)

HOUSEHOLD_VISIT_QUESTION_IDS = dict(
    num_using_fp={
        'mvp-sauri': 'num_using_fp',
        'mvp-potou': 'num_using_fp',
    },
    num_ec={
        'mvp-sauri': 'num_ec',
        'mvp-potou': 'num_ec',
    }
)

CHILD_CLOSE_FORM_QUESTION_IDS = dict(
    close_reason={
        'mvp-sauri': 'reason',
        'mvp-potou': 'termination_reason',
    },
    date_of_death={
        'mvp-sauri': 'date_of_death',
        'mvp-potou': 'date_of_death',
    }
)

PREGNANCY_CLOSE_FORM_QUESTION_IDS = dict(
    close_reason={
        'mvp-sauri': 'close_reason',
        'mvp-potou': 'close_reason'
    },
    pregnancy_termination={
        'mvp-sauri': 'date_of_termination',
        'mvp-potou': 'date_of_termination',
    }
)

class Command(LabelCommand):
    help = "Create the indicator definitions necessary to compute MVP Indicators."
    args = ""
    label = ""

    def handle(self, *args, **options):
        all_indicators = DocumentIndicatorDefinition.view("indicators/indicator_definitions",
            reduce=False,
            include_docs=True,
            startkey=["namespace domain slug", MVP.NAMESPACE],
            endkey=["namespace domain slug", MVP.NAMESPACE, {}]
        ).all()
        for ind in all_indicators:
            ind.delete()

        for domain in MVP.DOMAINS:
            shared_args=(
                MVP.NAMESPACE,
                domain
            )
            shared_kwargs = dict(
                version=1
            )

            self.create_form_alias_indicators(CHILD_CLOSE_FORM_QUESTION_IDS,
                MVP.VISIT_FORMS.get('child_visit'), domain, shared_args, shared_kwargs)
            self.create_form_alias_indicators(CHILD_VISIT_QUESTION_IDS,
                MVP.VISIT_FORMS.get('child_visit'), domain, shared_args, shared_kwargs)
            self.create_form_alias_indicators(HOUSEHOLD_VISIT_QUESTION_IDS,
                MVP.VISIT_FORMS.get('household_visit'), domain, shared_args, shared_kwargs)
            self.create_form_alias_indicators(PREGNANCY_VISIT_QUESTION_IDS,
                MVP.VISIT_FORMS.get('pregnancy_visit'), domain, shared_args, shared_kwargs)

            self.create_form_alias_indicators(CHILD_CLOSE_FORM_QUESTION_IDS,
                MVP.CLOSE_FORMS.get('child_close'), domain, shared_args, shared_kwargs)
            self.create_form_alias_indicators(PREGNANCY_CLOSE_FORM_QUESTION_IDS,
                MVP.CLOSE_FORMS.get('pregnancy_close'), domain, shared_args, shared_kwargs)

            pregnancy_edd = CaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="pregnancy_edd",
                xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                case_property="edd_calc",
                **shared_kwargs
            )
            pregnancy_edd.save()

            pregnancy_end = CaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="pregnancy_end",
                xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                case_property="closed_on",
                **shared_kwargs
            )
            pregnancy_end.save()

            child_visit_referral_type_quid = CHILD_VISIT_QUESTION_IDS.get('referral_type', {}).get(domain)
            if child_visit_referral_type_quid:
                child_case_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="referral_type",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('child_visit'),
                    question_id=child_visit_referral_type_quid,
                    **shared_kwargs
                )
                child_case_referral_type.save()

            pregnancy_visit_referral_type_quid = PREGNANCY_VISIT_QUESTION_IDS.get('referral_type', {}).get(domain)
            if pregnancy_visit_referral_type_quid:
                pregnancy_case_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="referral_type",
                    case_type='pregnancy',
                    xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                    question_id=pregnancy_visit_referral_type_quid,
                    **shared_kwargs
                )
                pregnancy_case_referral_type.save()

            visit_hospital_quid = CHILD_VISIT_QUESTION_IDS.get('visit_hospital', {}).get(domain)
            if visit_hospital_quid:
                visit_hospital_case = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="visit_hospital",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('child_visit'),
                    question_id=visit_hospital_quid,
                    **shared_kwargs
                )
                visit_hospital_case.save()

            immediate_danger_sign_quid = CHILD_VISIT_QUESTION_IDS.get('immediate_danger_sign', {}).get(domain)
            if immediate_danger_sign_quid:
                immediate_danger_sign_case = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="immediate_danger_sign",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('child_visit'),
                    question_id=immediate_danger_sign_quid,
                    **shared_kwargs
                )
                immediate_danger_sign_case.save()

            self.insert_dob_into_form('child_dob', MVP.VISIT_FORMS.get('child_visit'),
                shared_args, shared_kwargs)

            self.insert_dob_into_form('child_dob', MVP.CLOSE_FORMS.get('child_close'),
                shared_args, shared_kwargs)


    def insert_dob_into_form(self, indicator_slug, xmlns, shared_args, shared_kwargs):
        child_dob = CaseDataInFormIndicatorDefinition.update_or_create_unique(
            *shared_args,
            slug=indicator_slug,
            xmlns=xmlns,
            case_property="dob_calc",
            **shared_kwargs
        )
        child_dob.save()


    def create_form_alias_indicators(self, question_ids, xmlns, domain, shared_args, shared_kwargs):
        for indicator_slug, ids_per_domain in question_ids.items():
            question_id = ids_per_domain.get(domain)
            if question_id:
                form_question = FormDataAliasIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug=indicator_slug,
                    xmlns=xmlns,
                    question_id=question_id,
                    **shared_kwargs
                )
                form_question.save()