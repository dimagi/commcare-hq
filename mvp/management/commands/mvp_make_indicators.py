from django.core.management.base import LabelCommand
from corehq.apps.indicators.models import (CaseDataInFormIndicatorDefinition, FormDataAliasIndicatorDefinition,
                                           FormDataInCaseIndicatorDefinition, DocumentIndicatorDefinition)
from mvp.models import MVP
from mvp.static_definitions.question_id_mapping import (CHILD_CLOSE_FORM_QUESTION_IDS, CHILD_VISIT_QUESTION_IDS,
                                                        HOUSEHOLD_VISIT_QUESTION_IDS, PREGNANCY_VISIT_QUESTION_IDS,
                                                        PREGNANCY_CLOSE_FORM_QUESTION_IDS)

class Command(LabelCommand):
    help = "Create the indicator definitions necessary to compute MVP Indicators."
    args = ""
    label = ""

    def handle(self, *args, **options):
        for domain in MVP.DOMAINS:
            shared_args=(
                MVP.NAMESPACE,
                domain
            )

            # All the visit forms
            self.create_form_alias_indicators(CHILD_VISIT_QUESTION_IDS,
                MVP.VISIT_FORMS.get('child_visit'), domain, shared_args)
            self.create_form_alias_indicators(HOUSEHOLD_VISIT_QUESTION_IDS,
                MVP.VISIT_FORMS.get('household_visit'), domain, shared_args)
            self.create_form_alias_indicators(PREGNANCY_VISIT_QUESTION_IDS,
                MVP.VISIT_FORMS.get('pregnancy_visit'), domain, shared_args)

            # All the close forms
            self.create_form_alias_indicators(CHILD_CLOSE_FORM_QUESTION_IDS,
                MVP.CLOSE_FORMS.get('child_close'), domain, shared_args)
            self.create_form_alias_indicators(PREGNANCY_CLOSE_FORM_QUESTION_IDS,
                MVP.CLOSE_FORMS.get('pregnancy_close'), domain, shared_args)

            pregnancy_edd = CaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="pregnancy_edd",
                xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                case_property="edd_calc",
                version=1
            )
            print pregnancy_edd

            pregnancy_end = CaseDataInFormIndicatorDefinition.update_or_create_unique(
                *shared_args,
                slug="pregnancy_end",
                xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                case_property="closed_on",
                version=1
            )
            print pregnancy_end

            child_visit_referral = CHILD_VISIT_QUESTION_IDS.get('referral_type', {}).get(domain)
            if child_visit_referral:
                child_case_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="referral_type",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('child_visit'),
                    **child_visit_referral
                )
                print child_case_referral_type

            pregnancy_visit_referral = PREGNANCY_VISIT_QUESTION_IDS.get('referral_type', {}).get(domain)
            if pregnancy_visit_referral:
                pregnancy_case_referral_type = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="referral_type",
                    case_type='pregnancy',
                    xmlns=MVP.VISIT_FORMS.get('pregnancy_visit'),
                    **pregnancy_visit_referral
                )
                print pregnancy_case_referral_type

            visit_hospital = CHILD_VISIT_QUESTION_IDS.get('visit_hospital', {}).get(domain)
            if visit_hospital:
                visit_hospital_case = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="visit_hospital",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('child_visit'),
                    **visit_hospital
                )
                print visit_hospital_case

            immediate_danger_sign = CHILD_VISIT_QUESTION_IDS.get('immediate_danger_sign', {}).get(domain)
            if immediate_danger_sign:
                immediate_danger_sign_case = FormDataInCaseIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug="immediate_danger_sign",
                    case_type='child',
                    xmlns=MVP.VISIT_FORMS.get('child_visit'),
                    **immediate_danger_sign
                )
                print immediate_danger_sign_case

            self.insert_dob_into_form('child_dob', MVP.VISIT_FORMS.get('child_visit'),
                shared_args)

            self.insert_dob_into_form('child_dob', MVP.CLOSE_FORMS.get('child_close'),
                shared_args)


    def insert_dob_into_form(self, indicator_slug, xmlns, shared_args, version=1):
        child_dob = CaseDataInFormIndicatorDefinition.update_or_create_unique(
            *shared_args,
            slug=indicator_slug,
            xmlns=xmlns,
            case_property="dob_calc",
            version=version
        )
        print child_dob


    def create_form_alias_indicators(self, question_ids, xmlns, domain, shared_args):
        for indicator_slug, ids_per_domain in question_ids.items():
            indicator_info = ids_per_domain.get(domain)
            if indicator_info:
                form_question = FormDataAliasIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug=indicator_slug,
                    xmlns=xmlns,
                    **indicator_info
                )
                print form_question

    def _delete_existing(self):
        print "DELETING ALL INDICATORS"
        all_indicators = DocumentIndicatorDefinition.view("indicators/indicator_definitions",
            reduce=False,
            include_docs=True,
            startkey=["namespace domain slug", MVP.NAMESPACE],
            endkey=["namespace domain slug", MVP.NAMESPACE, {}]
        ).all()
        for ind in all_indicators:
            ind.delete()
