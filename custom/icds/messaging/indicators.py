import pytz
from datetime import datetime, timedelta
from corehq.apps.reports.analytics.esaccessors import get_last_submission_time_for_users
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

DEFAULT_LANGUAGE = 'hin'


class SMSIndicator(object):
    template = None

    @property
    @memoized
    def timezone(self):
        return pytz.timezone('Asia/Kolkata')

    @property
    @memoized
    def now(self):
        return datetime.now(tz=self.timezone)

    def should_send(self):
        """
        Should return True if the indicator requires a notification that should
        be sent, False if not.
        """
        raise NotImplementedError()

    def get_messages(self):
        """
        Should return a list of messages that should be sent. This is only relevant
        if self.should_send() returns True.
        """
        raise NotImplementedError()

    def render_template(self, language_code, context):
        try:
            return self._render_template(language_code, context)
        except TemplateDoesNotExist:
            return self._render_template(DEFAULT_LANGUAGE, context)

    def _render_template(self, language_code, context):
        template_name = 'icds/messaging/indicators/%s/%s' % (language_code, self.template)
        return render_to_string(template_name, context).strip()


class AWWIndicator(SMSIndicator):
    domain = None
    user = None

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user


class AWWSubmissionPerformanceIndicator(AWWIndicator):
    template = 'aww_no_submissions.txt'
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

    def should_send(self):
        return (
            not self.last_submission_date or
            (self.now.date() - self.last_submission_date).days > 7
        )

    def get_messages(self, language_code):
        more_than_one_week = False
        more_than_one_month = False

        if not self.last_submission_date:
            more_than_one_month = True
        else:
            days_since_submission = (self.now.date() - self.last_submission_date).days
            if days_since_submission > 7:
                more_than_one_week = True

        context = {
            'more_than_one_week': more_than_one_week,
            'more_than_one_month': more_than_one_month,
            'awc': self.user.sql_location.name,
        }

        message = self.render_template(language_code, context)

        return [message]
