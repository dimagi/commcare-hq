from __future__ import print_function
from __future__ import absolute_import
import dateutil
from django.core.management.base import BaseCommand
from corehq.apps.indicators.models import DynamicIndicatorDefinition
from corehq.apps.users.models import CommCareUser
from dimagi.utils.dates import DateSpan
from mvp.models import MVP


class Command(BaseCommand):
    help = "Returns the value of the indicator slug in the domain, given the parameters"

    def add_arguments(self, parser):
        parser.add_argument(
            'domain',
        )
        parser.add_argument(
            'indicator',
        )
        parser.add_argument(
            'startdate',
            type=dateutil.parser.parse,
        )
        parser.add_argument(
            'enddate',
            type=dateutil.parser.parse,
        )

    def handle(self, domain, indicator, startdate, enddate, **options):
        self.datespan = DateSpan(startdate, enddate)
        self.domain = domain
        self.user_ids = [user.user_id for user in CommCareUser.by_domain(self.domain)]
        self.get_indicator_response(indicator)

    def get_indicator_response(self, indicator_slug):
        indicator = DynamicIndicatorDefinition.get_current(MVP.NAMESPACE, self.domain, indicator_slug,
                    wrap_correctly=True)
        result = indicator.get_value(self.user_ids, datespan=self.datespan)
        print(result)
