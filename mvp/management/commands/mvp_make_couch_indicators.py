from django.core.management.base import LabelCommand
from corehq.apps.indicators.models import (DynamicIndicatorDefinition, CouchIndicatorDef,
                                           CombinedCouchViewIndicatorDefinition,
                                           MedianCouchIndicatorDef,
                                           CountUniqueCouchIndicatorDef,
                                           SumLastEmittedCouchIndicatorDef)
from mvp.models import (MVP, MVPDaysSinceLastTransmission, MVPChildCasesByAgeIndicatorDefinition,
                        MVPActiveCasesIndicatorDefinition)

from mvp.static_definitions.composite import COMPOSITE_INDICATORS
from mvp.static_definitions.couch.births import BIRTH_INDICATORS, ACTIVE_CHILD_CASES_BY_AGE_INDICATORS, COUNT_UNIQUE_BIRTH_INDICATORS
from mvp.static_definitions.couch.child_health import CHILD_HEALTH_INDICATORS, COUNT_UNIQUE_CHILD_HEALTH_INDICATORS
from mvp.static_definitions.couch.chw_referrals import CHW_REFERRAL_INDICATORS, MEDIAN_CHW_REFERRAL_INDICATORS
from mvp.static_definitions.couch.chw_visits import CHW_VISIT_ACTIVE_CASES_INDICATORS, CHW_VISITS_UNIQUE_COUNT_INDICATORS, CHW_VISIT_INDICATORS
from mvp.static_definitions.couch.deaths import DEATH_INDICATORS
from mvp.static_definitions.couch.maternal_health import MATERNAL_HEALTH_INDICATORS, SUM_LAST_UNIQUE_MATERNAL_HEALTH_INDICATORS, COUNT_UNIQUE_MATERNAL_HEALTH_INDICATORS
from mvp.static_definitions.couch.over5 import OVER5_HEALTH_INDICATORS

SIMPLE_COUCH_VIEW_INDICATORS = [
    BIRTH_INDICATORS,
    CHILD_HEALTH_INDICATORS,
    CHW_REFERRAL_INDICATORS,
    DEATH_INDICATORS,
    MATERNAL_HEALTH_INDICATORS,
    OVER5_HEALTH_INDICATORS,
    CHW_VISIT_INDICATORS,
]

# use with MedianCouchIndicatorDef
MEDIAN_INDICATORS = [
    MEDIAN_CHW_REFERRAL_INDICATORS
]

# Use with MVPActiveCasesIndicatorDefinition
ACTIVE_CASES_INDICATORS = [
    CHW_VISIT_ACTIVE_CASES_INDICATORS
]

# Use with MVPChildCasesByAgeIndicatorDefinition
ACTIVE_CHILD_CASES_INDICATORS = [
    ACTIVE_CHILD_CASES_BY_AGE_INDICATORS,
]

# Use with CountUniqueCouchIndicatorDef
COUNT_UNIQUE_INDICATORS = [
    CHW_VISITS_UNIQUE_COUNT_INDICATORS,
    COUNT_UNIQUE_CHILD_HEALTH_INDICATORS,
    COUNT_UNIQUE_MATERNAL_HEALTH_INDICATORS,
    COUNT_UNIQUE_BIRTH_INDICATORS,
]

# use with SumLastEmittedCouchIndicatorDef
SUM_LAST_UNIQUE_INICATORS = [
    SUM_LAST_UNIQUE_MATERNAL_HEALTH_INDICATORS,
]

class Command(LabelCommand):
    help = "Create the indicator definitions necessary to compute MVP Indicators."
    args = ""
    label = ""

    def handle(self, *args, **options):
        all_indicators = DynamicIndicatorDefinition.view("indicators/dynamic_indicator_definitions",
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

            self.create_indicators_of_type(CouchIndicatorDef,
                SIMPLE_COUCH_VIEW_INDICATORS,
                shared_args, shared_kwargs)

            self.create_indicators_of_type(MedianCouchIndicatorDef,
                MEDIAN_INDICATORS,
                shared_args, shared_kwargs)

            self.create_indicators_of_type(MVPActiveCasesIndicatorDefinition,
                ACTIVE_CASES_INDICATORS,
                shared_args, shared_kwargs)

            self.create_indicators_of_type(MVPChildCasesByAgeIndicatorDefinition,
                ACTIVE_CHILD_CASES_INDICATORS,
                shared_args, shared_kwargs)

            self.create_indicators_of_type(CountUniqueCouchIndicatorDef,
                COUNT_UNIQUE_INDICATORS,
                shared_args, shared_kwargs)

            self.create_indicators_of_type(SumLastEmittedCouchIndicatorDef,
                SUM_LAST_UNIQUE_INICATORS,
                shared_args, shared_kwargs)

            for indicator_slug, indicator_kwargs in COMPOSITE_INDICATORS.items():
                indicator_kwargs.update(shared_kwargs)
                indicator_def = CombinedCouchViewIndicatorDefinition.update_or_create_unique(
                    *shared_args,
                    slug=indicator_slug,
                    **indicator_kwargs
                )
                indicator_def.save()

            days_since_last_transmission = MVPDaysSinceLastTransmission.update_or_create_unique(
                *shared_args,
                slug="days_since_last_transmission",
                description="Days since last transmission",
                title="Days since last transmission"
            )
            days_since_last_transmission.save()

    def create_indicators_of_type(self, indicator_type_class, static_defs,
                                  shared_args, shared_kwargs):
        for app_indicators in static_defs:
            mvp_app = app_indicators['app']
            for couch_view, indicator_defs in app_indicators['indicators'].items():
                for indicator_slug, indicator_kwargs in indicator_defs.items():
                    indicator_kwargs.update(shared_kwargs)
                    indicator_def = indicator_type_class.update_or_create_unique(
                        *shared_args,
                        slug=indicator_slug,
                        couch_view="%s/%s" % (mvp_app, couch_view),
                        **indicator_kwargs
                    )
                    indicator_def.save()
