import dateutil
from django.core.management.base import BaseCommand
from corehq.apps.indicators.models import DynamicIndicatorDefinition
from corehq.apps.users.models import CommCareUser
from dimagi.utils.dates import DateSpan
from mvp.models import MVP


class Command(BaseCommand):
    help = "Returns the value of the indicator slug in the domain, given the parameters"
    args = '<domain> <indicator> <startdate> <enddate>'

    def handle(self, *args, **options):
        startdate = dateutil.parser.parse(args[2])
        enddate = dateutil.parser.parse(args[3])
        self.datespan = DateSpan(startdate, enddate)
        self.domain = args[0]
        self.user_ids = [user.user_id for user in CommCareUser.by_domain(self.domain)]
        self.get_indicator_response(args[1])

    def get_indicator_response(self, indicator_slug):
        indicator = DynamicIndicatorDefinition.get_current(MVP.NAMESPACE, self.domain, indicator_slug,
                    wrap_correctly=True)
        result = indicator.get_value(self.user_ids, datespan=self.datespan)
        print result
