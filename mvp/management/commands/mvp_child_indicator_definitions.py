from django.core.management.base import LabelCommand, CommandError
from corehq.apps.indicators.models import IndicatorDefinition, CaseDataInFormIndicatorDefinition, FormDataAliasIndicatorDefinition
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

            for indicator_slug, ids_per_domain in MVP.FORM_QUESTION_IDS.items():
                # Question ID Aliases
                question_id = ids_per_domain.get(domain)
                if question_id:
                    form_question = FormDataAliasIndicatorDefinition.update_or_create_unique(
                        slug=indicator_slug,
                        xmlns=MVP.FORMS.get('child_visit'),
                        question_id=question_id,
                        **shared_kwargs
                    )
                    form_question.save()

            child_dob = CaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="child_dob",
                xmlns=MVP.FORMS.get('child_visit'),
                case_property="dob_calc",
                **shared_kwargs
            )
            child_dob.save()

            household_child_dob = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="household_child_dob",
                xmlns=MVP.FORMS.get('household_visit'),
                case_property="dob_calc",
                related_case_type = "child",
                **shared_kwargs
            )
            household_child_dob.save()

            household_child_close_reason = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="household_child_close_reason",
                xmlns=MVP.FORMS.get('household_visit'),
                case_property="close_reason",
                related_case_type = "child",
                **shared_kwargs
            )
            household_child_close_reason.save()

            household_pregnancy_visit = MVPRelatedCaseDataInFormIndicatorDefinition.update_or_create_unique(
                slug="household_pregnancy_visit",
                xmlns=MVP.FORMS.get('household_visit'),
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

