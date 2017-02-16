from collections import defaultdict
import pytz
from datetime import datetime, timedelta
from corehq.apps.reports.analytics.esaccessors import (
    get_last_submission_time_for_users,
    get_last_form_submissions_by_user,
)
from dimagi.utils.dates import DateSpan
from dimagi.utils.decorators.memoized import memoized
from dimagi.utils.parsing import string_to_datetime
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from corehq.apps.locations.dbaccessors import (
    assigned_location_by_user_id,
    get_users_location_ids,
)
from corehq.apps.locations.models import SQLLocation
from custom.icds.const import VHND_SURVEY_XMLNS

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
    @property
    @memoized
    def child_locations(self):
        return self.user.sql_location.child_locations()

    @property
    @memoized
    def awc_locations(self):
        return {l.location_id: l.name for l in self.child_locations}

    @property
    @memoized
    def locations_by_user_id(self):
        return assigned_location_by_user_id(self.domain, set(self.awc_locations))

    @property
    @memoized
    def aww_user_ids(self):
        return set(self.locations_by_user_id.keys())

    @property
    @memoized
    def user_ids_by_location_id(self):
        user_ids_by_location_id = defaultdict(set)
        for u_id, locations in self.locations_by_user_id.items():
            for loc_id in locations:
                user_ids_by_location_id[loc_id].add(u_id)

        return user_ids_by_location_id

    def location_names_from_user_id(self, user_ids):
        loc_names = set()
        for u_id in user_ids:
            for l_id in self.locations_by_user_id.get(u_id, []):
                loc_names.add(self.awc_locations[l_id])
        return loc_names


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

        if more_than_one_week or more_than_one_month:
            context = {
                'more_than_one_week': more_than_one_week,
                'more_than_one_month': more_than_one_month,
                'awc': self.user.sql_location.name,
            }
            return [self.render_template(context, language_code=language_code)]

        return []


class LSSubmissionPerformanceIndicator(LSIndicator):
    template = 'ls_no_submissions.txt'

    def __init__(self, domain, user):
        super(LSSubmissionPerformanceIndicator, self).__init__(domain, user)

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
            one_week_loc_names = self.location_names_from_user_id(one_week_user_ids)
            week_context = {'location_names': ', '.join(one_week_loc_names), 'timeframe': 'week'}
            messages.append(self.render_template(week_context, language_code=language_code))

        if one_month_user_ids:
            one_month_loc_names = self.location_names_from_user_id(one_month_user_ids)
            month_context = {'location_names': ','.join(one_month_loc_names), 'timeframe': 'month'}
            messages.append(self.render_template(month_context, language_code=language_code))

        return messages


class LSVHNDSurveyIndicator(LSIndicator):
    template = 'ls_vhnd_survey.txt'

    def __init__(self, domain, user):
        super(LSVHNDSurveyIndicator, self).__init__(domain, user)

        self.forms = get_last_form_submissions_by_user(
            domain, self.aww_user_ids, xmlns=VHND_SURVEY_XMLNS
        )

    def get_messages(self, language_code=None):
        def convert_to_date(date):
            return string_to_datetime(date).date() if date else None

        now_date = self.now.date()
        user_ids_with_forms_in_time_frame = set()
        for user_id, form in self.forms.items():
            vhnd_date = convert_to_date(form['form']['vhsnd_date_planned'])
            if (now_date - vhnd_date).days < 37:
                user_ids_with_forms_in_time_frame.add(user_id)

        user_ids_without_forms = self.aww_user_ids - user_ids_with_forms_in_time_frame

        awc_ids = {
            loc
            for loc, user_ids in self.user_ids_by_location_id.items()
            if user_ids.isdisjoint(user_ids_with_forms_in_time_frame)
        }
        messages = []

        if awc_ids:
            awc_names = {self.awc_locations[awc] for awc in awc_ids}
            context = {'location_names': ', '.join(awc_names)}
            messages.append(self.render_template(context, language_code=language_code))

        return messages
