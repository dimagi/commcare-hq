from __future__ import print_function
from __future__ import absolute_import
from django.core.management.base import BaseCommand
from corehq.apps.indicators.utils import get_indicator_config
from mvp.models import (
    CLASS_PATH,
    MVPDaysSinceLastTransmission,
    MVPActiveCasesIndicatorDefinition,
    MVPChildCasesByAgeIndicatorDefinition,
)


class Command(BaseCommand):
    help = "Resets the class path for the MVP indicator type specified"

    def handle(self, **options):
        indicator_types = [
            MVPDaysSinceLastTransmission,
            MVPActiveCasesIndicatorDefinition,
            MVPChildCasesByAgeIndicatorDefinition,
        ]
        indicator_config = get_indicator_config()
        for indicator_type in indicator_types:
            for domain, namespaces in indicator_config.items():
                for namespace in namespaces:
                    all_of_type = indicator_type.get_all_of_type(
                        namespace[0], domain
                    )
                    for indicator in all_of_type:
                        print (
                            "reset class path of %(old_path)s for indicator "
                            "%(slug)s in %(domain)s to %(new_path)s" % {
                                'old_path': indicator.class_path,
                                'slug': indicator.slug,
                                'domain': indicator.domain,
                                'new_path': CLASS_PATH,
                            })
                        indicator.class_path = CLASS_PATH
                        indicator.save()
