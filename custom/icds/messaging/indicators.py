import math
from datetime import datetime, timedelta

from django.conf import settings
from django.db import connections
from django.db.models import Max
from django.template import TemplateDoesNotExist
from django.template.loader import render_to_string

import pytz
from lxml import etree
from memoized import memoized

from casexml.apps.phone.models import OTARestoreCommCareUser
from dimagi.utils.couch import CriticalSection

from corehq.apps.app_manager.dbaccessors import get_app, get_build_by_version
from corehq.apps.app_manager.fixtures.mobile_ucr import (
    ReportFixturesProviderV1,
)
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.userreports.models import StaticDataSourceConfiguration
from corehq.apps.userreports.util import get_table_name
from corehq.sql_db.connections import connection_manager
from corehq.util.quickcache import quickcache
from corehq.util.soft_assert import soft_assert
from custom.icds.const import (
    CHILDREN_WEIGHED_REPORT_ID,
    DAYS_AWC_OPEN_REPORT_ID,
    HOME_VISIT_REPORT_ID,
    SUPERVISOR_APP_ID,
    THR_REPORT_ID,
    UCR_V2_AG_ALIAS,
    UCR_V2_AG_MONTHLY_ALIAS,
    UCR_V2_CBE_LAST_MONTH_ALIAS,
    UCR_V2_LS_DAYS_AWC_OPEN_ALIAS,
    UCR_V2_LS_TIMELY_HOME_VISITS_ALIAS,
    UCR_V2_MPR_5_CCS_RECORD_ALIAS,
    UCR_V2_MPR_5_CHILD_HEALTH_CASES_MONTHLY_ALIAS,
    UCR_V2_MPR_5_CHILD_HEALTH_PT1_ALIAS,
)
from custom.icds_reports.cache import icds_quickcache
from custom.icds_reports.models.aggregate import AggregateInactiveAWW

DEFAULT_LANGUAGE = 'hin'

REPORT_IDS = [
    HOME_VISIT_REPORT_ID,
    THR_REPORT_ID,
    CHILDREN_WEIGHED_REPORT_ID,
    DAYS_AWC_OPEN_REPORT_ID,
]

REPORT_ALIASES = [
    UCR_V2_AG_ALIAS,
    UCR_V2_AG_MONTHLY_ALIAS,
    UCR_V2_CBE_LAST_MONTH_ALIAS,
    UCR_V2_LS_DAYS_AWC_OPEN_ALIAS,
    UCR_V2_MPR_5_CCS_RECORD_ALIAS,
    UCR_V2_MPR_5_CHILD_HEALTH_CASES_MONTHLY_ALIAS,
    UCR_V2_MPR_5_CHILD_HEALTH_PT1_ALIAS,
    UCR_V2_LS_TIMELY_HOME_VISITS_ALIAS,
]


@quickcache(['domain'], timeout=4 * 60 * 60, memoize_timeout=4 * 60 * 60)
def get_latest_report_configs(domain):
    # ToDo: might need to pass version here to fetch necessary report configs
    app = get_app(domain, SUPERVISOR_APP_ID, latest=True)
    return {
        report_config.report_id: report_config
        for module in app.get_report_modules()
        for report_config in module.report_configs
        if report_config.report_id in REPORT_IDS
    }


@quickcache(['domain', 'app_version'], timeout=4 * 60 * 60, memoize_timeout=4 * 60 * 60)
def get_v2_report_configs(domain, app_version):
    if app_version:
        app = get_build_by_version(domain, SUPERVISOR_APP_ID, app_version)
    else:
        app = get_app(domain, SUPERVISOR_APP_ID, latest=True)
    return {
        report_config.report_slug: report_config
        for module in app.get_report_modules()
        for report_config in module.report_configs
        if report_config.report_slug in REPORT_ALIASES
    }


@quickcache(['domain', 'report_id', 'ota_user.user_id'], timeout=12 * 60 * 60)
def _get_cached_report_fixture_for_user(domain, report_id, ota_user):
    """
    :param domain: the domain
    :param report_id: the index to the result from get_latest_report_configs()
    :param ota_user: the OTARestoreCommCareUser for which to get the report fixture
    """
    report_config = get_latest_report_configs(domain)[report_id]
    [xml] = ReportFixturesProviderV1().report_config_to_fixture(
        report_config, ota_user
    )
    return etree.tostring(xml)


@quickcache(['domain', 'report_slug', 'ota_user.user_id', 'app_version'], timeout=12 * 60 * 60)
def _get_cached_v2_report_fixture_for_user(domain, report_slug, ota_user, app_version):
    """
    :param domain: the domain
    :param report_slug: the alias to the result from get_v2_report_configs()
    :param ota_user: the OTARestoreCommCareUser for which to get the report fixture
    """
    report_config = get_v2_report_configs(domain, app_version)[report_slug]
    # ToDo: should we be using ReportFixturesProviderV2?
    [xml] = ReportFixturesProviderV1().report_config_to_fixture(
        report_config, ota_user
    )
    return etree.tostring(xml)


def get_report_fixture_for_user(domain, report_id, ota_user):
    """
    The Element objects used by the lxml library don't cache properly.
    So instead we cache the XML string and convert back here.
    """
    return etree.fromstring(_get_cached_report_fixture_for_user(domain, report_id, ota_user))


def get_v2_report_fixture_for_user(domain, report_slug, ota_user, app_version):
    """
    The Element objects used by the lxml library don't cache properly.
    So instead we cache the XML string and convert back here.
    """
    return etree.fromstring(_get_cached_v2_report_fixture_for_user(domain, report_slug, ota_user, app_version))


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


class BaseAWWAggregatePerformanceIndicator(AWWIndicator):
    def get_messages(self, language_code=None):
        raise NotImplementedError()

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


class AWWAggregatePerformanceIndicator(BaseAWWAggregatePerformanceIndicator):
    template = 'aww_aggregate_performance.txt'
    slug = 'aww_2'

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


class AWWAggregatePerformanceIndicatorV2(BaseAWWAggregatePerformanceIndicator):
    template = 'aww_aggregate_performance_v2.txt'
    slug = 'aww_v2'

    def get_rows_count_from_fixture(self, fixture):
        count = 0
        xpath = './rows/row[@is_total_row="False"]'
        rows = fixture.findall(xpath)
        location_name = self.user.sql_location.name
        for row in rows:
            owner_id = row.find('./column[@id="awc_id"]')
            if owner_id.text == location_name:
                count += 1
        return count

    def get_messages(self, language_code=None):
        # ToDo: return if language_code or if template does not exist for language_code
        from custom.icds.messaging.custom_content import get_reported_last_build_of_app_by_user
        if self.supervisor is None:
            return []

        supervisor_user_last_build = get_reported_last_build_of_app_by_user(SUPERVISOR_APP_ID, self.supervisor)
        supervisor_user_app_version = None
        if supervisor_user_last_build:
            supervisor_user_app_version = supervisor_user_last_build.build_version
        ls_agg_perf_indicator = LSAggregatePerformanceIndicatorV2(self.domain, self.supervisor,
                                                                  supervisor_user_app_version)
        data = _get_data_for_performance_indicator(self, ls_agg_perf_indicator)
        return [self.render_template(data, language_code=language_code)]


# All process_sms tasks should hopefully be finished in 4 hours
@quickcache([], timeout=60 * 60 * 4)
def is_aggregate_inactive_aww_data_fresh(send_email=False):
    # Heuristic to check if collect_inactive_awws task ran succesfully today or yesterday
    #   This would return False if both today and yesterday's task failed
    #   or if the last-submission is older than a day due to pillow lag.
    last_submission = AggregateInactiveAWW.objects.filter(
        last_submission__isnull=False
    ).aggregate(Max('last_submission'))['last_submission__max']
    if not last_submission:
        return False
    is_fresh = last_submission >= (datetime.today() - timedelta(days=1)).date()
    SMS_TEAM = ['{}@{}'.format('icds-sms-rule', 'dimagi.com')]
    if not send_email:
        return is_fresh
    _soft_assert = soft_assert(to=SMS_TEAM, send_to_ops=False)
    if is_fresh:
        _soft_assert(False, "The weekly inactive SMS rule is successfully triggered for this week")
    else:
        _soft_assert(False,
            "The weekly inactive SMS rule is skipped for this week as latest_submission {} data is older than one day"
            .format(str(last_submission))
        )
    return is_fresh


class AWWSubmissionPerformanceIndicator(AWWIndicator):
    template = 'aww_no_submissions.txt'
    last_submission_date = None
    slug = 'aww_1'

    def __init__(self, domain, user):
        super(AWWSubmissionPerformanceIndicator, self).__init__(domain, user)

        result = AggregateInactiveAWW.objects.filter(
            awc_id=user.location_id).values('last_submission').first()
        if result:
            self.last_submission_date = result['last_submission']

    def get_messages(self, language_code=None):
        if not is_aggregate_inactive_aww_data_fresh(send_email=True):
            return []

        more_than_one_week = False
        more_than_one_month = False
        one_month_ago = (datetime.utcnow() - timedelta(days=30)).date()
        one_week_ago = (datetime.utcnow() - timedelta(days=7)).date()

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

        self.should_send_sms = bool(get_awcs_with_old_vhnd_date(domain, [self.user.location_id]))

    def get_messages(self, language_code=None):
        if self.should_send_sms:
            return [self.render_template({}, language_code=language_code)]
        else:
            return []


def _get_last_submission_dates(awc_ids):
    return {
        row['awc_id']: row['last_submission']
        for row in AggregateInactiveAWW.objects.filter(
        awc_id__in=awc_ids).values('awc_id', 'last_submission').all()
    }


class LSSubmissionPerformanceIndicator(LSIndicator):
    template = 'ls_no_submissions.txt'
    slug = 'ls_6'

    def __init__(self, domain, user):
        super(LSSubmissionPerformanceIndicator, self).__init__(domain, user)

        self.last_submission_dates = _get_last_submission_dates(awc_ids=set(self.awc_locations))

    def get_messages(self, language_code=None):
        messages = []
        one_week_loc_ids = []
        one_month_loc_ids = []

        now_date = self.now.date()
        for loc_id in self.awc_locations:
            last_sub_date = self.last_submission_dates.get(loc_id)
            if not last_sub_date:
                one_month_loc_ids.append(loc_id)
            else:
                days_since_submission = (now_date - last_sub_date).days
                if days_since_submission > 7:
                    one_week_loc_ids.append(loc_id)

        if one_week_loc_ids:
            one_week_loc_names = {self.awc_locations[loc_id] for loc_id in one_week_loc_ids}
            week_context = {'location_names': ', '.join(one_week_loc_names), 'timeframe': 'week'}
            messages.append(self.render_template(week_context, language_code=language_code))

        if one_month_loc_ids:
            one_month_loc_names = {self.awc_locations[loc_id] for loc_id in one_month_loc_ids}
            month_context = {'location_names': ','.join(one_month_loc_names), 'timeframe': 'month'}
            messages.append(self.render_template(month_context, language_code=language_code))

        return messages


class LSVHNDSurveyIndicator(LSIndicator):
    template = 'ls_vhnd_survey.txt'
    slug = 'ls_2'

    def __init__(self, domain, user):
        super(LSVHNDSurveyIndicator, self).__init__(domain, user)

        self.awc_ids_not_in_timeframe = get_awcs_with_old_vhnd_date(
            domain,
            set(self.awc_locations)
        )

    def get_messages(self, language_code=None):
        messages = []

        if self.awc_ids_not_in_timeframe:
            awc_names = {self.awc_locations[awc] for awc in self.awc_ids_not_in_timeframe}
            context = {'location_names': ', '.join(awc_names)}
            messages.append(self.render_template(context, language_code=language_code))

        return messages


def get_awcs_with_old_vhnd_date(domain, awc_location_ids):
    return set(awc_location_ids) - get_awws_in_vhnd_timeframe(domain)


@icds_quickcache(
    ['domain'], timeout=12 * 60 * 60, memoize_timeout=12 * 60 * 60, session_function=None,
    skip_arg=lambda *args: settings.UNIT_TESTING)
def get_awws_in_vhnd_timeframe(domain):
    # This function is called concurrently by many tasks.
    # The CriticalSection ensures that the expensive operation is not triggered
    #   by each task again, the compute_awws_in_vhnd_timeframe itself is cached separately,
    #   so that other waiting tasks could lookup the value from cache.
    with CriticalSection(['compute_awws_in_vhnd_timeframe']):
        return compute_awws_in_vhnd_timeframe(domain)


@icds_quickcache(
    ['domain'], timeout=60 * 60, memoize_timeout=60 * 60, session_function=None,
    skip_arg=lambda *args: settings.UNIT_TESTING)
def compute_awws_in_vhnd_timeframe(domain):
    """
    This computes awws with vhsnd_date_past_month less than 37 days.

    Result is cached in local memory, so that indvidual reminder tasks
    per AWW/LS dont hit the database each time
    """
    table = get_table_name(domain, 'static-vhnd_form')
    query = """
    SELECT DISTINCT awc_id
    FROM "{table}"
    WHERE vhsnd_date_past_month > %(37_days_ago)s
    """.format(table=table)
    cutoff = datetime.now(tz=pytz.timezone('Asia/Kolkata')).date()
    query_params = {"37_days_ago": cutoff - timedelta(days=37)}

    datasource_id = StaticDataSourceConfiguration.get_doc_id(domain, 'static-vhnd_form')
    data_source = StaticDataSourceConfiguration.by_id(datasource_id)
    django_db = connection_manager.get_django_db_alias(data_source.engine_id)
    with connections[django_db].cursor() as cursor:
        cursor.execute(query, query_params)
        return {row[0] for row in cursor.fetchall()}


class BaseLSAggregatePerformanceIndicator(LSIndicator):
    def get_messages(self, language_code=None):
        raise NotImplementedError()

    @property
    @memoized
    def restore_user(self):
        return OTARestoreCommCareUser(self.domain, self.user)

    def get_report_fixture(self, report_id):
        raise NotImplementedError()

    def get_value_from_fixture(self, fixture, attribute):
        xpath = './rows/row[@is_total_row="True"]/column[@id="{}"]'.format(attribute)
        try:
            return fixture.findall(xpath)[0].text
        except:
            raise IndicatorError("{} not found in fixture {} for user {}".format(
                attribute, fixture, self.user.get_id
            ))


class LSAggregatePerformanceIndicator(BaseLSAggregatePerformanceIndicator):
    template = 'ls_aggregate_performance.txt'
    slug = 'ls_1'

    def get_report_fixture(self, report_id):
        return get_report_fixture_for_user(self.domain, report_id, self.restore_user)

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


class LSAggregatePerformanceIndicatorV2(BaseLSAggregatePerformanceIndicator):
    template = 'ls_aggregate_performance_v2.txt'
    slug = 'ls_v2'

    def __init__(self, domain, user, app_version):
        super().__init__(domain, user)
        self.app_version = app_version

    def get_report_fixture(self, report_id):
        return get_v2_report_fixture_for_user(self.domain, report_id, self.restore_user, self.app_version)

    def get_messages(self, language_code=None):
        # ToDo: return if language_code or if template does not exist for language_code
        data = _get_data_for_performance_indicator(self, self)
        num_awc_locations = len(self.awc_locations)
        num_days_open = data.pop('num_days_open', 0)
        num_days_open = int(num_days_open) if num_days_open else 0
        avg_days_open = 0
        if num_awc_locations:
            avg_days_open = int(round(num_days_open / num_awc_locations))

        data.update({
            "avg_days_open": avg_days_open,
        })
        return [self.render_template(data, language_code=language_code)]

    def get_rows_count_from_fixture(self, fixture):
        xpath = './rows/row[@is_total_row="False"]'
        rows = fixture.findall(xpath)
        return len(rows)

    @property
    @memoized
    def ucr_v2_ls_timely_home_visits_fixture(self):
        return self.get_report_fixture(UCR_V2_LS_TIMELY_HOME_VISITS_ALIAS)

    @property
    @memoized
    def ucr_v2_mpr_5_ccs_record_fixture(self):
        return self.get_report_fixture(UCR_V2_MPR_5_CCS_RECORD_ALIAS)

    @property
    @memoized
    def ucr_v2_mpr_5_child_health_pt1_fixture(self):
        return self.get_report_fixture(UCR_V2_MPR_5_CHILD_HEALTH_PT1_ALIAS)

    @property
    @memoized
    def ucr_v2_mpr_5_child_health_cases_monthly_fixture(self):
        return self.get_report_fixture(UCR_V2_MPR_5_CHILD_HEALTH_CASES_MONTHLY_ALIAS)

    @property
    @memoized
    def ucr_v2_ls_days_awc_open_fixture(self):
        return self.get_report_fixture(UCR_V2_LS_DAYS_AWC_OPEN_ALIAS)

    @property
    @memoized
    def ucr_v2_ag_monthly_fixture(self):
        return self.get_report_fixture(UCR_V2_AG_MONTHLY_ALIAS)

    @property
    @memoized
    def ucr_v2_ag_fixture(self):
        return self.get_report_fixture(UCR_V2_AG_ALIAS)

    @property
    @memoized
    def ucr_v2_cbe_last_month_fixture(self):
        return self.get_report_fixture(UCR_V2_CBE_LAST_MONTH_ALIAS)


def _get_data_for_performance_indicator(indicator_obj, ls_indicator_obj):
    visits = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_ls_timely_home_visits_fixture, 'count')

    count_bp = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_ccs_record_fixture, 'count_bp')
    count_ebf = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_ccs_record_fixture, 'count_ebf')
    count_cf = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_child_health_pt1_fixture,
                                                    'count_cf')
    count_pnc = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_ccs_record_fixture,
                                                     'count_pnc')
    visits_goal = math.ceil(
        (int(count_bp) * 0.44) + int(count_ebf) + (int(count_pnc) * 6) + (int(count_cf) * 0.39)
    )

    on_time_visits = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_ls_timely_home_visits_fixture,
                                                          'visit_on_time')

    ccs_gte_21 = (
        int(indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_ccs_record_fixture,
                                                 'thr_rations_gte_21'))
        + int(indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_child_health_pt1_fixture,
                                                   'thr_rations_gte_21'))
    )
    ccs_total = (
        int(indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_ccs_record_fixture,
                                                 'open_in_month'))
        + int(indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_mpr_5_child_health_pt1_fixture,
                                                   'open_in_month'))
    )
    weighed_num = indicator_obj.get_value_from_fixture(
        ls_indicator_obj.ucr_v2_mpr_5_child_health_cases_monthly_fixture, 'weighed_in_month')
    weighed_denom = indicator_obj.get_value_from_fixture(
        ls_indicator_obj.ucr_v2_mpr_5_child_health_cases_monthly_fixture, 'open_in_month')
    num_days_open = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_ls_days_awc_open_fixture,
                                                         'awc_opened_count')

    ag_services_gte21 = (
        int(indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_ag_monthly_fixture,
                                                 'thr_21_plus_days'))
        + int(indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_ag_monthly_fixture,
                                                   'hcm_21_plus_days'))
    )
    total_ag_oos = indicator_obj.get_value_from_fixture(ls_indicator_obj.ucr_v2_ag_fixture, 'out_of_school')
    cbe_conducted = indicator_obj.get_rows_count_from_fixture(ls_indicator_obj.ucr_v2_cbe_last_month_fixture)
    return {
        'visits': visits,
        'visits_goal': visits_goal,
        'on_time_visits': on_time_visits,
        'ccs_gte_21': ccs_gte_21,
        'ccs_total': ccs_total,
        'weighed_num': weighed_num,
        'weighed_denom': weighed_denom,
        'num_days_open': num_days_open,
        'ag_services_gte21': ag_services_gte21,
        'total_ag_oos': total_ag_oos,
        'cbe_conducted': cbe_conducted
    }
