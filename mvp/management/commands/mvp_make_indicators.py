from django.core.management.base import LabelCommand, CommandError
from corehq.apps.indicators.models import IndicatorDefinition, CaseDataInFormIndicatorDefinition, FormDataAliasIndicatorDefinition, FormDataInCaseIndicatorDefinition
from mvp.models import MVP, MVPRelatedCaseDataInFormIndicatorDefinition, MVPRelatedCaseDataInCaseIndicatorDefinition



class Command(LabelCommand):
    help = "Create the indicator definitions necessary to compute MVP Indicators."
    args = ""
    label = ""

    def handle(self, *args, **options):
        all_indicators = IndicatorDefinition.view("indicators/indicator_definitions",
            reduce=False,
            include_docs=True,
            startkey=["namespace domain slug", MVP.NAMESPACE],
            endkey=["namespace domain slug", MVP.NAMESPACE, {}]
        ).all()
        for ind in all_indicators:
            ind.delete()

        for domain in MVP.DOMAINS:
            shared_kwargs = dict(
                namespace=MVP.NAMESPACE,
                domain=domain,
                version=1
            )

            for indicator_slug, ids_per_domain in MVP.CHILD_VISIT_QUESTION_IDS.items():
                # Question ID Aliases for child_vist forms
                question_id = ids_per_domain.get(domain)
                if question_id:
                    form_question = FormDataAliasIndicatorDefinition.update_or_create_unique(
                        slug=indicator_slug,
                        xmlns=MVP.VISIT_FORMS.get('child_visit'),
                        question_id=question_id,
                        **shared_kwargs
                    )
                    form_question.save()

            referral_type_question_id = MVP.CHILD_VISIT_QUESTION_IDS.get('referral_type', {}).get(domain)
            if referral_type_question_id:
                alias_referral_type_preg = FormDataAliasIndicatorDefinition.update_or_create_unique(
                    slug="referral_type",
                    xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                    question_id=referral_type_question_id,
                    **shared_kwargs
                )
                alias_referral_type_preg.save()

                preg_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    slug="referral_type",
                    case_type='pregnancy',
                    xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                    question_id=referral_type_question_id,
                    **shared_kwargs
                )
                preg_referral_type.save()

                child_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    slug="referral_type",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('chiild_visit'),
                    question_id=referral_type_question_id,
                    **shared_kwargs
                )
                child_referral_type.save()

            for indicator_slug, ids_per_domain in MVP.PREGNANCY_VISIT_QUESTION_IDS.items():
                # Form Data in Pregnancy Case
                question_id = ids_per_domain.get(domain)
                if question_id:
                    form_data_in_case = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                        slug=indicator_slug,
                        case_type='pregnancy',
                        xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                        question_id=question_id
                        **shared_kwargs
                    )
                    form_data_in_case.save()

            for indicator_slug, ids_per_domain in MVP.HOUSEHOLD_VISIT_QUESTION_IDS.items():
                question_id = ids_per_domain.get(domain)
                if question_id:
                    form_data_in_case = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                        slug=indicator_slug,
                        case_type='household',
                        xmlns=MVP.VISIT_FORMS.get('household_visit'),
                        question_id=question_id,
                        **shared_kwargs
                    )
                    form_data_in_case.save()




            child_dob = CaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="child_dob",
                xmlns=MVP.VISIT_FORMS.get('child_visit'),
                case_property="dob_calc",
                **shared_kwargs
            )
            child_dob.save()

            household_child_dob = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="household_child_dob",
                xmlns=MVP.VISIT_FORMS.get('household_visit'),
                case_property="dob_calc",
                related_case_type = "child",
                **shared_kwargs
            )
            household_child_dob.save()

            household_child_close_reason = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="household_child_close_reason",
                xmlns=MVP.VISIT_FORMS.get('household_visit'),
                case_property="close_reason",
                related_case_type = "child",
                **shared_kwargs
            )
            household_child_close_reason.save()

            household_pregnancy_visit = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="household_pregnancy_visit",
                xmlns=MVP.VISIT_FORMS.get('household_visit'),
                case_property="dob_calc",
                related_case_type = "pregnancy",
                **shared_kwargs
            )
            household_pregnancy_visit.save()

            case_pregnancy = MVPRelatedCaseDataInCaseIndicatorDefinition.update_or_create_unique(
                slug="case_pregnancy",
                case_type="household",
                related_case_property="dob_calc",
                related_case_type = "pregnancy",
                **shared_kwargs
            )
            case_pregnancy.save()

            case_child_dob = MVPRelatedCaseDataInCaseIndicatorDefinition.update_or_create_unique(
                slug="case_child_dob",
                case_type="household",
                related_case_property="dob_calc",
                related_case_type = "child",
                **shared_kwargs
            )
            case_child_dob.save()

            case_child_close_reason = MVPRelatedCaseDataInCaseIndicatorDefinition.update_or_create_unique(
                slug="case_child_close_reason",
                case_type="household",
                related_case_property="close_reason",
                related_case_type = "child",
                **shared_kwargs
            )
            case_child_close_reason.save()

