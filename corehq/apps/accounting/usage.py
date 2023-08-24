import calendar
import datetime

from corehq.apps.accounting.models import FeatureType
from corehq.apps.smsbillables.models import SmsBillable
from corehq.apps.users.models import CommCareUser, WebUser


class FeatureUsageCalculator(object):

    def __init__(self, feature_rate, domain_name,
                 start_date=None, end_date=None):
        super(FeatureUsageCalculator, self).__init__()
        self.feature_rate = feature_rate
        self.domain = domain_name
        today = datetime.date.today()
        last_day = calendar.monthrange(today.year, today.month)[1]
        self.start_date = start_date or datetime.date(
            today.year, today.month, 1)
        self.end_date = end_date or datetime.date(
            today.year, today.month, last_day)

    def get_usage(self):
        try:
            return {
                FeatureType.USER: self._get_user_usage(),
                FeatureType.SMS: self._get_sms_usage(),
                FeatureType.WEB_USER: self._get_web_user_usage(),
            }[self.feature_rate.feature.feature_type]
        except KeyError:
            pass

    def _get_user_usage(self):
        return CommCareUser.total_by_domain(self.domain, is_active=True)

    def _get_sms_usage(self):
        return SmsBillable.objects.filter(
            domain__exact=self.domain,
            is_valid=True,
            date_sent__gte=self.start_date,
            date_sent__lt=self.end_date + datetime.timedelta(days=1),
        ).count()

    def _get_web_user_usage(self):
        web_user_in_account = set(WebUser.ids_by_domain(self.domain))
        return len(web_user_in_account)
