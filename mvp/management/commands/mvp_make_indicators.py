from django.core.management.base import LabelCommand, CommandError
from corehq.apps.indicators.models import IndicatorDefinition, CaseDataInFormIndicatorDefinition, FormDataAliasIndicatorDefinition, FormDataInCaseIndicatorDefinition, DocumentIndicatorDefinition
from mvp.models import MVP, MVPRelatedCaseDataInFormIndicatorDefinition, MVPRelatedCaseDataInCaseIndicatorDefinition

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
        'mvp-sauri': 'patient_available.fever_medication',
        'mvp-potou': 'patient_available.medication_type'
    },
    diarrhea_medication={
        'mvp-sauri': 'patient_available.diarrhea_medication',
        'mvp-potou': 'patient_available.medication_type'
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
        'mvp-potou': 'prev_num_anc'
    },
    num_anc={
        'mvp-sauri': 'group_counseling.num_anc',
        'mvp-potou': 'group_counseling.num_anc',
        },
    last_anc_date={
        'mvp-sauri': 'group_counseling.last_anc_date',
        },
    last_anc_weeks={
        'mvp-potou': 'group_counseling.last_anc_weeks'
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

            for indicator_slug, ids_per_domain in CHILD_VISIT_QUESTION_IDS.items():
                # Question ID Aliases for child_vist forms
                question_id = ids_per_domain.get(domain)
                if question_id:
                    form_question = FormDataAliasIndicatorDefinition.update_or_create_unique(
                        *shared_args,
                        slug=indicator_slug,
                        xmlns=MVP.VISIT_FORMS.get('child_visit'),
                        question_id=question_id,
                        **shared_kwargs
                    )
                    form_question.save()

            for indicator_slug, ids_per_domain in HOUSEHOLD_VISIT_QUESTION_IDS.items():
                # Question ID Aliases for household_visit forms
                question_id = ids_per_domain.get(domain)
                if question_id:
                    form_question = FormDataAliasIndicatorDefinition.update_or_create_unique(
                        *shared_args,
                        slug=indicator_slug,
                        xmlns=MVP.VISIT_FORMS.get('household_visit'),
                        question_id=question_id,
                        **shared_kwargs
                    )
                    form_question.save()

            for indicator_slug, ids_per_domain in PREGNANCY_VISIT_QUESTION_IDS.items():
                # Question ID Aliases for pregnancy_visit forms
                question_id = ids_per_domain.get(domain)
                if question_id:
                    form_data_in_case = FormDataAliasIndicatorDefinition.update_or_create_unique(
                        *shared_args,
                        slug=indicator_slug,
                        xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                        question_id=question_id,
                        **shared_kwargs
                    )
                    form_data_in_case.save()

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


            # everything related to referral_type
            referral_type_question_id = CHILD_VISIT_QUESTION_IDS.get('referral_type', {}).get(domain)
            if referral_type_question_id:
                alias_referral_type_preg = FormDataAliasIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="referral_type",
                    xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                    question_id=referral_type_question_id,
                    **shared_kwargs
                )
                alias_referral_type_preg.save()

                preg_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="referral_type",
                    case_type='pregnancy',
                    xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                    question_id=referral_type_question_id,
                    **shared_kwargs
                )
                preg_referral_type.save()

                child_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="referral_type",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('chiild_visit'),
                    question_id=referral_type_question_id,
                    **shared_kwargs
                )
                child_referral_type.save()


            child_dob = CaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="child_dob",
                xmlns=MVP.VISIT_FORMS.get('child_visit'),
                case_property="dob_calc",
                **shared_kwargs
            )
            child_dob.save()

            household_child_dob = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="household_child_dob",
                xmlns=MVP.VISIT_FORMS.get('household_visit'),
                case_property="dob_calc",
                related_case_type = "child",
                **shared_kwargs
            )
            household_child_dob.save()

            household_child_close_reason = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="household_child_close_reason",
                xmlns=MVP.VISIT_FORMS.get('household_visit'),
                case_property="close_reason",
                related_case_type = "child",
                **shared_kwargs
            )
            household_child_close_reason.save()

            household_pregnancy_visit = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="household_pregnancy_visit",
                xmlns=MVP.VISIT_FORMS.get('household_visit'),
                case_property="dob_calc",
                related_case_type = "pregnancy",
                **shared_kwargs
            )
            household_pregnancy_visit.save()

            case_pregnancy = MVPRelatedCaseDataInCaseIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="case_pregnancy",
                case_type="household",
                related_case_property="dob_calc",
                related_case_type = "pregnancy",
                **shared_kwargs
            )
            case_pregnancy.save()

            case_child_dob = MVPRelatedCaseDataInCaseIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="case_child_dob",
                case_type="household",
                related_case_property="dob_calc",
                related_case_type = "child",
                **shared_kwargs
            )
            case_child_dob.save()

            case_child_close_reason = MVPRelatedCaseDataInCaseIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="case_child_close_reason",
                case_type="household",
                related_case_property="close_reason",
                related_case_type = "child",
                **shared_kwargs
            )
            case_child_close_reason.save()
