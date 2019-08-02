from __future__ import absolute_import
from __future__ import division
from __future__ import unicode_literals
from collections import defaultdict
from datetime import datetime, timedelta

import pytz

from django.conf import settings
from django.db.models import Max
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

from casexml.apps.phone.models import OTARestoreCommCareUser
from dimagi.utils.dates import DateSpan
from memoized import memoized
from dimagi.utils.parsing import string_to_datetime

from corehq.apps.app_manager.dbaccessors import get_app
from corehq.apps.app_manager.fixtures.mobile_ucr import ReportFixturesProvider
from corehq.apps.app_manager.models import ReportModule
from corehq.apps.locations.dbaccessors import (
    get_user_ids_from_primary_location_ids,
    get_users_by_location_id,
)
from corehq.apps.reports.analytics.esaccessors import (
    get_last_submission_time_for_users,
    get_last_form_submissions_by_user,
)
from corehq.util.quickcache import quickcache
from corehq.warehouse.models.facts import ApplicationStatusFact
from corehq.warehouse.utils import get_warehouse_latest_modified_date
from custom.icds.const import (
    CHILDREN_WEIGHED_REPORT_ID,
    DAYS_AWC_OPEN_REPORT_ID,
    HOME_VISIT_REPORT_ID,
    SUPERVISOR_APP_ID,
    THR_REPORT_ID,
    VHND_SURVEY_XMLNS,
)
from lxml import etree

DEFAULT_LANGUAGE = 'hin'

REPORT_IDS = [
    HOME_VISIT_REPORT_ID,
    THR_REPORT_ID,
    CHILDREN_WEIGHED_REPORT_ID,
    DAYS_AWC_OPEN_REPORT_ID,
]


@quickcache(['domain'], timeout=4 * 60 * 60, memoize_timeout=4 * 60 * 60)
def get_report_configs(domain):
    app = get_app(domain, SUPERVISOR_APP_ID, latest=True)
    return {
        report_config.report_id: report_config
        for module in app.get_report_modules()
        for report_config in module.report_configs
        if report_config.report_id in REPORT_IDS
    }


@quickcache(['domain', 'report_id', 'ota_user.user_id'], timeout=12 * 60 * 60)
def _get_report_fixture_for_user(domain, report_id, ota_user):
    """
    :param domain: the domain
    :param report_id: the index to the result from get_report_configs()
    :param ota_user: the OTARestoreCommCareUser for which to get the report fixture
    """
    xml = ReportFixturesProvider.report_config_to_v1_fixture(
        get_report_configs(domain)[report_id], ota_user
    )
    return etree.tostring(xml)


def get_report_fixture_for_user(domain, report_id, ota_user):
    """
    The Element objects used by the lxml library don't cache properly.
    So instead we cache the XML string and convert back here.
    """
    return etree.fromstring(_get_report_fixture_for_user(domain, report_id, ota_user))


class IndicatorError(Exception):
    pass


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

    # This is used to identify the indicator in the SMS data
    slug = None

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
    @property
    @memoized
    def supervisor(self):
        """
        Returns None if there is a misconfiguration (i.e., if the AWW's location
        has no parent location, or if there are no users at the parent location).
        """
        supervisor_location = self.user.sql_location.parent
        if supervisor_location is None:
            return None

        return get_users_by_location_id(self.domain, supervisor_location.location_id).first()


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
        return get_user_ids_from_primary_location_ids(self.domain, set(self.awc_locations))

    @property
    @memoized
    def aww_user_ids(self):
        return set(self.locations_by_user_id.keys())

    @property
    @memoized
    def user_ids_by_location_id(self):
        user_ids_by_location_id = defaultdict(set)
        for u_id, loc_id in self.locations_by_user_id.items():
            user_ids_by_location_id[loc_id].add(u_id)

        return user_ids_by_location_id

    def location_names_from_user_id(self, user_ids):
        loc_ids = {self.locations_by_user_id.get(u) for u in user_ids}
        return {self.awc_locations[l] for l in loc_ids}


class AWWAggregatePerformanceIndicator(AWWIndicator):
    template = 'aww_aggregate_performance.txt'
    slug = 'aww_2'

    def get_value_from_fixture(self, fixture, attribute):
        xpath = './rows/row[@is_total_row="False"]'
        rows = fixture.findall(xpath)
        location_name = self.user.sql_location.name
        for row in rows:
            owner_id = row.find('./column[@id="owner_id"]')
            if owner_id.text == location_name:
                try:
                    return row.find('./column[@id="{}"]'.format(attribute)).text
                except:
                    raise IndicatorError(
                        "Attribute {} not found in restore for AWC {}".format(attribute, location_name)
                    )

        return 0

    def get_messages(self, language_code=None):
        if self.supervisor is None:
            return []

        agg_perf = LSAggregatePerformanceIndicator(self.domain, self.supervisor)

        visits = self.get_value_from_fixture(agg_perf.visits_fixture, 'count')
        on_time_visits = self.get_value_from_fixture(agg_perf.visits_fixture, 'visit_on_time')
        thr_gte_21 = self.get_value_from_fixture(agg_perf.thr_fixture, 'open_ccs_thr_gte_21')
        thr_count = self.get_value_from_fixture(agg_perf.thr_fixture, 'open_count')
        num_weigh = self.get_value_from_fixture(agg_perf.weighed_fixture, 'open_weighed')
        num_weigh_avail = self.get_value_from_fixture(agg_perf.weighed_fixture, 'open_count')
        num_days_open = self.get_value_from_fixture(agg_perf.days_open_fixture, 'awc_opened_count')

        context = {
            "visits": visits,
            "on_time_visits": on_time_visits,
            "thr_distribution": "{} / {}".format(thr_gte_21, thr_count),
            "children_weighed": "{} / {}".format(num_weigh, num_weigh_avail),
            "days_open": num_days_open,
        }

        return [self.render_template(context, language_code=language_code)]


class AWWSubmissionPerformanceIndicator(AWWIndicator):
    template = 'aww_no_submissions.txt'
    last_submission_date = None
    slug = 'aww_1'

    def __init__(self, domain, user):
        super(AWWSubmissionPerformanceIndicator, self).__init__(domain, user)

        self.last_submission_date = ApplicationStatusFact.objects.filter(
            user_dim__user_id=user.get_id,
            domain=domain,
        ).aggregate(value=Max("last_form_submission_date"))["value"]

    def get_messages(self, language_code=None):
        # default 24 hours
        ACCEPTABLE_WAREHOUSE_LAG_IN_MINUTES = getattr(settings, 'ACCEPTABLE_WAREHOUSE_LAG_IN_MINUTES', 60 * 24)
        warehouse_lag = (datetime.utcnow() - get_warehouse_latest_modified_date()).total_seconds() / 60
        if warehouse_lag > ACCEPTABLE_WAREHOUSE_LAG_IN_MINUTES:
            return []

        more_than_one_week = False
        more_than_one_month = False
        one_month_ago = datetime.utcnow() - timedelta(days=30)
        one_week_ago = datetime.utcnow() - timedelta(days=7)

        if not self.last_submission_date or self.last_submission_date < one_month_ago:
            more_than_one_month = True
        elif self.last_submission_date < one_week_ago:
            more_than_one_week = True

        if more_than_one_week or more_than_one_month:
            context = {
                'more_than_one_week': more_than_one_week,
                'more_than_one_month': more_than_one_month,
                'awc': self.user.sql_location.name,
            }
            return [self.render_template(context, language_code=language_code)]

        return []


class AWWVHNDSurveyIndicator(AWWIndicator):
    template = 'aww_vhnd_survey.txt'
    slug = 'phase2_aww_1'

    def __init__(self, domain, user):
        super(AWWVHNDSurveyIndicator, self).__init__(domain, user)

        self.forms = get_last_form_submissions_by_user(
            domain, [self.user.get_id], xmlns=VHND_SURVEY_XMLNS
        )

    def get_messages(self, language_code=None):
        now_date = self.now.date()
        for forms in self.forms.values():
            vhnd_date = forms[0]['form'].get('vhsnd_date_past_month')
            if vhnd_date is None:
                continue
            if (now_date - string_to_datetime(vhnd_date).date()).days < 37:
                # AWW has VHND form submission in last 37 days -> no message
                return []

        return [self.render_template({}, language_code=language_code)]


class LSSubmissionPerformanceIndicator(LSIndicator):
    template = 'ls_no_submissions.txt'
    slug = 'ls_6'

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
    slug = 'ls_2'

    def __init__(self, domain, user):
        super(LSVHNDSurveyIndicator, self).__init__(domain, user)

        self.forms = get_last_form_submissions_by_user(
            domain, self.aww_user_ids, xmlns=VHND_SURVEY_XMLNS
        )

    def get_messages(self, language_code=None):
        now_date = self.now.date()
        user_ids_with_forms_in_time_frame = set()
        for user_id, forms in self.forms.items():
            vhnd_date = forms[0]['form'].get('vhsnd_date_past_month')
            if vhnd_date is None:
                continue
            if (now_date - string_to_datetime(vhnd_date).date()).days < 37:
                user_ids_with_forms_in_time_frame.add(user_id)

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


class LSAggregatePerformanceIndicator(LSIndicator):
    template = 'ls_aggregate_performance.txt'
    slug = 'ls_1'

    @property
    @memoized
    def restore_user(self):
        return OTARestoreCommCareUser(self.domain, self.user)

    def get_report_fixture(self, report_id):
        return get_report_fixture_for_user(self.domain, report_id, self.restore_user)

    def clear_caches(self):
        get_report_configs.clear(self.domain)
        for report_id in REPORT_IDS:
            get_report_fixture_for_user.clear(self.domain, report_id, self.restore_user)

    @property
    @memoized
    def visits_fixture(self):
        return self.get_report_fixture(HOME_VISIT_REPORT_ID)

    @property
    @memoized
    def thr_fixture(self):
        return self.get_report_fixture(THR_REPORT_ID)

    @property
    @memoized
    def weighed_fixture(self):
        return self.get_report_fixture(CHILDREN_WEIGHED_REPORT_ID)

    @property
    @memoized
    def days_open_fixture(self):
        return self.get_report_fixture(DAYS_AWC_OPEN_REPORT_ID)

    def get_value_from_fixture(self, fixture, attribute):
        xpath = './rows/row[@is_total_row="True"]/column[@id="{}"]'.format(attribute)
        try:
            return fixture.findall(xpath)[0].text
        except:
            raise IndicatorError("{} not found in fixture {} for user {}".format(
                attribute, fixture, self.user.get_id
            ))

    def get_messages(self, language_code=None):
        on_time_visits = self.get_value_from_fixture(self.visits_fixture, 'visit_on_time')
        visits = self.get_value_from_fixture(self.visits_fixture, 'count')
        thr_gte_21 = self.get_value_from_fixture(self.thr_fixture, 'open_ccs_thr_gte_21')
        thr_count = self.get_value_from_fixture(self.thr_fixture, 'open_count')
        num_weigh = self.get_value_from_fixture(self.weighed_fixture, 'open_weighed')
        num_weigh_avail = self.get_value_from_fixture(self.weighed_fixture, 'open_count')
        num_days_open = int(self.get_value_from_fixture(self.days_open_fixture, 'awc_opened_count'))
        num_awc_locations = len(self.awc_locations)
        if num_awc_locations:
            avg_days_open = int(round(num_days_open / num_awc_locations))
        else:
            # catch div by 0
            avg_days_open = 0

        context = {
            "on_time_visits": on_time_visits,
            "visits": visits,
            "visits_goal": num_awc_locations * 65,
            "thr_distribution": "{} / {}".format(thr_gte_21, thr_count),
            "children_weighed": "{} / {}".format(num_weigh, num_weigh_avail),
            "days_open": "{}".format(avg_days_open),
        }

        return [self.render_template(context, language_code=language_code)]
