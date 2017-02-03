import pytz
from datetime import datetime, timedelta
from corehq.apps.reports.analytics.esaccessors import get_last_submission_time_for_users
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized


class SMSIndicator(object):

    @property
    @memoized
    def timezone(self):
        return pytz.timezone('Asia/Kolkata')

    @property
    @memoized
    def now(self):
        return datetime.now(tz=self.timezone)

    def requires_notification(self):
        raise NotImplementedError()

    def get_content(self):
        raise NotImplementedError()


class AWWIndicator(SMSIndicator):
    domain = None
    user = None

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user


class AWWSubmissionPerformanceIndicator(AWWIndicator):
    last_submission_date = None

    def __init__(self, domain, user):
        super(AWWSubmissionPerformanceIndicator, self).__init__(domain, user)

        result = get_last_submission_time_for_users(self.domain, [self.user.get_id], self.get_datespan())
        self.last_submission_date = result.get(self.user.get_id)

    def get_datespan(self):
        today = datetime(self.now.year, self.now.month, self.now.day)
        end_date = today + timedelta(days=1)
        start_date = today - timedelta(days=30)
        return DateSpan(start_date, end_date, timezone=self.timezone)

    def requires_notification(self):
        return (
            not self.last_submission_date or
            (self.now.date() - self.last_submission_date).days > 7
        )

    def get_content(self):
        if not self.last_submission_date:
            time_since = "in the last 30 days"
        else:
            days_since_submission = (self.now.date() - self.last_submission_date).days
            if days_since_submission > 28:
                time_since = "in the last 4 weeks"
            elif days_since_submission > 21:
                time_since = "in the last 3 weeks"
            elif days_since_submission > 14:
                time_since = "in the last 2 weeks"
            else:
                time_since = "in the last 1 week"

        return "AWC has not submitted any forms %s" % time_since
