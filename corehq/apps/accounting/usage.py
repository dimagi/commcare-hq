import calendar
import datetime
from corehq.apps.accounting.models import FeatureType
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.users.models import CommCareUser


class FeatureUsage(object):

    def __init__(self, feature_rate, domain_name):
        super(FeatureUsage, self).__init__()
        self.feature_rate = feature_rate
        self.domain = domain_name

    def get_usage(self):
        try:
            return {
                FeatureType.USER: self._get_user_usage(),
                FeatureType.SMS: self._get_sms_usage(),
            }[self.feature_rate.feature.feature_type]
        except KeyError:
            pass

    def _get_user_usage(self):
        return CommCareUser.total_by_domain(self.domain, is_active=True)

    def _get_sms_usage(self):
        today = datetime.date.today()
        _, last_day = calendar.monthrange(today.year, today.month)
        first_of_month = datetime.date(today.year, today.month, 1)
        last_of_month = datetime.date(today.year, today.month, last_day)
        return SmsBillable.objects.filter(
            domain__exact=self.domain,
            is_valid=True,
            date_sent__range=[first_of_month, last_of_month]
        ).count()
