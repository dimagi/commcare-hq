import pytz
from datetime import datetime, timedelta
from corehq.apps.reports.analytics.esaccessors import get_last_submission_time_for_users
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from corehq.apps.locations.dbaccessors import (
    get_users_location_ids,
    user_ids_at_locations,
)
from corehq.apps.locations.models import SQLLocation

DEFAULT_LANGUAGE = 'hin'


class SMSIndicator(object):
    # The name of the template to be used when rendering the message(s) to be sent
    # This should not be the full path, just the name of the file, since the path
    # is determined at runtime by language code
    template = None

    # The domain this indicator is being run in
    domain = None

    # The user the indicator is being run for
    # For AWWIndicator, this is the AWW CommCareUser
    # For LSIndicator, this is the LS CommCareUser
    user = None

    def __init__(self, domain, user):
        self.domain = domain
        self.user = user

    @property
    @memoized
    def timezone(self):
        return pytz.timezone('Asia/Kolkata')

    @property
    @memoized
    def now(self):
        return datetime.now(tz=self.timezone)

    def get_messages(self, language_code=None):
        """
        Should return a list of messages that should be sent.
        """
        raise NotImplementedError()

    def render_template(self, context, language_code=None):
        if not language_code:
            return self._render_template(context, DEFAULT_LANGUAGE)

        try:
            return self._render_template(context, language_code)
        except TemplateDoesNotExist:
            return self._render_template(context, DEFAULT_LANGUAGE)

    def _render_template(self, context, language_code):
        template_name = 'icds/messaging/indicators/%s/%s' % (language_code, self.template)
        return render_to_string(template_name, context).strip()


class AWWIndicator(SMSIndicator):
    pass


class LSIndicator(SMSIndicator):
    pass


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

    def get_messages(self, language_code=None):
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

        if more_than_one_week or more_than_one_month:
            return [self.render_template(context, language_code=language_code)]

        return []


class LSSubmissionPerformanceIndicator(LSIndicator):
    template = 'ls_no_submissions.txt'

    def __init__(self, domain, user):
        super(LSSubmissionPerformanceIndicator, self).__init__(domain, user)

        child_locations = [l.location_id for l in self.user.sql_location.child_locations()]
        self.aww_user_ids = user_ids_at_locations(child_locations)
        self.last_submission_dates = get_last_submission_time_for_users(
            self.domain, self.aww_user_ids, self.get_datespan()
        )

    def get_datespan(self):
        today = datetime(self.now.year, self.now.month, self.now.day)
        end_date = today + timedelta(days=1)
        start_date = today - timedelta(days=30)
        return DateSpan(start_date, end_date, timezone=self.timezone)

    def get_messages(self, language_code=None):
        messages = []
        one_week_user_ids = []
        one_month_user_ids = []

        now_date = self.now.date()
        for user_id in self.aww_user_ids:
            last_sub_date = self.last_submission_dates.get(user_id)
            if not last_sub_date:
                one_month_user_ids.append(user_id)
            else:
                days_since_submission = (now_date - last_sub_date).days
                if days_since_submission > 7:
                    one_week_user_ids.append(user_id)

        if one_week_user_ids:
            one_week_loc_ids = get_users_location_ids(self.domain, one_week_user_ids)
            one_week_loc_names = (
                SQLLocation.objects.filter(location_id__in=one_week_loc_ids).values_list('name', flat=True)
            )
            week_context = {'location_names': ', '.join(one_week_loc_names), 'timeframe': 'week'}
            messages.append(self.render_template(week_context, language_code=language_code))

        if one_month_user_ids:
            one_month_loc_ids = get_users_location_ids(self.domain, one_month_user_ids)
            one_month_loc_names = (
                SQLLocation.objects.filter(location_id__in=one_month_loc_ids).values_list('name', flat=True)
            )
            month_context = {'location_names': ','.join(one_month_loc_names), 'timeframe': 'month'}
            messages.append(self.render_template(month_context, language_code=language_code))

        return messages
