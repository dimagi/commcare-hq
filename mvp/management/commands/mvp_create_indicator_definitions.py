from django.core.management.base import LabelCommand, CommandError
from corehq.apps.indicators.models import IndicatorDefinition, BooleanFormDataCaseIndicatorDefinition
from mvp.models import MVPLessThanAgeIndicatorDefinition, MVP, MVPDangerSignIndicatorDefinition

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
                version=2
            )

            under_five = MVPLessThanAgeIndicatorDefinition.update_or_create_unique(
                slug="under_five",
                case_type="child",
                related_case_types=["household"],
                age_in_months=5*12,
                **shared_kwargs
            )
            under_five.save()

            neonate_newborn = MVPLessThanAgeIndicatorDefinition.update_or_create_unique(
                slug="neonate_newborn",
                case_type="child",
                related_case_types=["household"],
                age_in_months=31,
                **shared_kwargs
            )
            neonate_newborn.save()

            rdt_received = BooleanFormDataCaseIndicatorDefinition.update_or_create_unique(
                slug="rdt_received",
                case_type="child",
                xmlns="http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A",
                compared_property="patient_available.referral_follow_on.referral_and_rdt",
                expression="'%(value)s' == 'yes'",
                **shared_kwargs
            )
            rdt_received.save()

            rdt_positive = BooleanFormDataCaseIndicatorDefinition.update_or_create_unique(
                slug="rdt_positive",
                case_type="child",
                xmlns="http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A",
                compared_property="patient_available.referral_follow_on.rdt_result",
                expression="'%(value)s' == 'positive'",
                **shared_kwargs
            )
            rdt_positive.save()

            antimalarial_received = BooleanFormDataCaseIndicatorDefinition.update_or_create_unique(
                slug="antimalarial_received",
                case_type="child",
                xmlns="http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A",
                compared_property="cur_meds_given",
                expression="'anti_malarial' in '%(value)s'",
                **shared_kwargs
            )
            antimalarial_received.save()

            danger_signs = MVPDangerSignIndicatorDefinition.update_or_create_unique(
                slug="danger_signs",
                case_type="child",
                xmlns="http://openrosa.org/formdesigner/B9CEFDCD-8068-425F-BA67-7DC897030A5A",
                **shared_kwargs
            )
            danger_signs.save()
