import datetime
from collections import defaultdict
import pytz
from xml.etree import ElementTree

from celery.task import periodic_task
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils.dateparse import parse_datetime

from casexml.apps.case.mock import CaseBlock
from corehq import toggles
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.soft_assert import soft_assert
from dimagi.utils.decorators.memoized import memoized

from .case_utils import CASE_TYPE_ADHERENCE, CASE_TYPE_EPISODE


DOSE_TAKEN_INDICATORS = [
    'directly_observed_dose',
    'unobserved_dose',
    'self_administered_dose',
]
DOSE_MISSED = 'missed_dose'
DOSE_UNKNOWN = 'missing_data'
DOSE_KNOWN_INDICATORS = DOSE_TAKEN_INDICATORS + [DOSE_MISSED]
DAILY_SCHEDULE_FIXTURE_NAME = 'adherence_schedules'
DAILY_SCHEDULE_ID = 'schedule_daily'
SCHEDULE_ID_FIXTURE = 'id'
logger = get_task_logger(__name__)


@periodic_task(
    run_every=crontab(day_of_week=[1], hour=0, minute=0),  # every Monday
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def enikshay_adherence_task():
    # runs adherence calculations for all domains that have `toggles.UATBC_ADHERENCE_TASK` enabled
    domains = toggles.UATBC_ADHERENCE_TASK.get_enabled_domains()
    for domain in domains:
        updater = EpisodeAdherenceUpdater(domain)
        updater.run()


class EpisodeAdherenceUpdater(object):
    """This iterates over all open 'episode' cases and sets 'adherence' related properties
    according to this spec https://docs.google.com/document/d/1FjSdLYOYUCRBuW3aSxvu3Z5kvcN6JKbpDFDToCgead8/edit

    This is applicable to various enikshay domains. The domain can be specified in the initalization
    """

    def __init__(self, domain):
        self.domain = domain
        self.purge_date = pytz.UTC.localize(datetime.datetime.today() - datetime.timedelta(days=60))

    def run(self):
        # iterate over all open 'episode' cases and set 'adherence' properties
        for episode in self._get_open_episode_cases():
            update = EpisodeUpdate(episode, self)
            try:
                case_block = update.case_block()
                if case_block:
                    submit_case_blocks(
                        [ElementTree.tostring(case_block.as_xml())],
                        self.domain
                    )
            except Exception, e:
                logger.error("Error calculating adherence values for episode case_id({}): {}".format(
                    episode.case_id,
                    e
                ))

    def _get_open_episode_cases(self):
        # return all open 'episode' cases
        case_accessor = CaseAccessors(self.domain)
        case_ids = case_accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_EPISODE)
        return case_accessor.iter_cases(case_ids)

    @memoized
    def get_doses_data(self):
        # return 'doses_per_week' by 'schedule_id' from the Fixture data
        fixtures = FixtureDataItem.get_indexed_items(self.domain, DAILY_SCHEDULE_FIXTURE_NAME, SCHEDULE_ID_FIXTURE)
        return dict((k, int(fixture['doses_per_week'])) for k, fixture in fixtures.items())


class EpisodeUpdate(object):
    """
    Class to capture adherence related calculations specific to an 'episode' case
    """
    def __init__(self, episode_case, case_updater):
        """
        Args:
            episode_case: An 'episode' case object
            case_repeater: EpisodeAdherenceUpdater object
        """
        self.episode = episode_case
        self.case_updater = case_updater

    def get_property(self, property):
        """
        Args:
            name of the case-property

        Returns:
            value of the episode case-property named 'property'
        """
        return self.episode.dynamic_case_properties().get(property)

    @memoized
    def get_valid_adherence_cases(self):
        case_accessor = CaseAccessors(self.case_updater.domain)
        indexed_cases = case_accessor.get_reverse_indexed_cases([self.episode.case_id])
        return [
            case
            for case in indexed_cases
            if (not case.closed and case.type == CASE_TYPE_ADHERENCE and
                case.dynamic_case_properties().get('adherence_value') in DOSE_KNOWN_INDICATORS)
        ]

    def get_latest_adherence_case_for_episode(self):
        """
        return open case of type 'adherence' reverse-indexed to episode that
            has the latest 'adherence_date' property of all
        """
        # sometime far back
        latest_date = pytz.UTC.localize(datetime.datetime(1990, 1, 1))
        latest_case = None
        for case in self.get_valid_adherence_cases():
            adherence_date = parse_datetime(case.dynamic_case_properties().get('adherence_date'))
            if adherence_date > latest_date:
                latest_date = adherence_date
                latest_case = case
        return latest_case

    def adherence_cases_between(self, cases, start_date, end_date):
        """
        Filter given 'adherence' cases between start_date, end_date

        Args:
            cases: List of 'adherence' cases

        Returns:
            List of cases that have 'adherence_date' between start_date and end_date

        """
        open_pertinent_adherence_cases = [
            case for case in cases
            if (
                start_date.astimezone(pytz.UTC) <=
                parse_datetime(case.dynamic_case_properties().get('adherence_date')).astimezone(pytz.UTC) <=
                end_date.astimezone(pytz.UTC))
        ]

        return open_pertinent_adherence_cases

    def count_doses_taken(self, adherence_cases):
        """
        Args:
            adherence_cases: list of 'adherence_cases' with its 'adherence_value' as one of DOSE_KNOWN_INDICATORS

        Returns:
            total count of adherence_cases excluding duplicates on a given day. If there are
            two adherence_cases on one day at different time, it will be counted as one
        """
        by_date = defaultdict(list)
        for case in adherence_cases:
            adherence_date = parse_datetime(case.dynamic_case_properties().get('adherence_date')).date()
            adherence_value = case.dynamic_case_properties().get('adherence_value')
            if adherence_value in DOSE_TAKEN_INDICATORS:
                by_date[adherence_date].append(case)

        return len(by_date.keys())

    def update_json(self):
        """
        Evaluates adherence calculations on the 'episode' case and returns dict of values

        Returns:
            If no update is necessary, empty dict is returned, if not, dict with following
            keys is returned

            {
                'aggregated_score_date_calculated': value,
                'expected_doses_taken': value,
                'aggregated_score_count_taken': value
            }
        """
        adherence_schedule_date_start = parse_datetime(self.get_property('adherence_schedule_date_start'))
        if not adherence_schedule_date_start:
            # adherence schedule hasn't been selected, so no update necessary
            return {}

        if adherence_schedule_date_start > self.case_updater.purge_date:
            update = {
                'aggregated_score_date_calculated': adherence_schedule_date_start - datetime.timedelta(days=1),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_total_doses_taken': 0,
                'adherence_latest_date_recorded': adherence_schedule_date_start - datetime.timedelta(days=1)
            }
        else:
            update = {}
            adherence_case = self.get_latest_adherence_case_for_episode()
            if not adherence_case:
                update["aggregated_score_date_calculated"] = adherence_schedule_date_start - datetime.timedelta(1)
                update["aggregated_score_count_taken"] = 0
                update["adherence_latest_date_recorded"] = adherence_schedule_date_start - datetime.timedelta(1)
                update["expected_doses_taken"] = 0
                update["adherence_total_doses_taken"] = 0
            else:
                adherence_date = parse_datetime(adherence_case.dynamic_case_properties().get('adherence_date'))
                update["adherence_latest_date_recorded"] = adherence_date
                if adherence_date < self.case_updater.purge_date:
                    update["aggregated_score_date_calculated"] = adherence_date
                else:
                    update["aggregated_score_date_calculated"] = self.case_updater.purge_date

                # calculate 'adherence_total_doses_taken'
                all_adherence_cases = self.get_valid_adherence_cases()
                update["adherence_total_doses_taken"] = self.count_doses_taken(all_adherence_cases)
                # calculate 'aggregated_score_count_taken'
                adherence_cases = self.adherence_cases_between(
                    all_adherence_cases,
                    adherence_schedule_date_start,
                    update["aggregated_score_date_calculated"]
                )
                update["aggregated_score_count_taken"] = self.count_doses_taken(adherence_cases)

                # calculate 'expected_doses_taken' score
                dose_data = self.case_updater.get_doses_data()
                adherence_schedule_id = self.get_property('adherence_schedule_id') or DAILY_SCHEDULE_ID
                doses_per_week = dose_data.get(adherence_schedule_id)
                if doses_per_week:
                    update['expected_doses_taken'] = ((
                        (update['aggregated_score_date_calculated'] - adherence_schedule_date_start)).days / 7.0
                    ) * doses_per_week
                else:
                    update['expected_doses_taken'] = 0
                    soft_assert(notify_admins=True)(
                        True,
                        "No fixture item found with schedule_id {}".format(adherence_schedule_id)
                    )
        # convert datetime -> date objects
        for key, val in update.iteritems():
            if isinstance(val, datetime.datetime):
                update[key] = val.date()
        return update

    def case_block(self):
        """
        Returns:
            CaseBlock object with adherence updates. If no update is necessary, None is returned
        """
        update = self.update_json()
        if update:
            return CaseBlock(**{
                'case_id': self.episode.case_id,
                'create': False,
                'update': update
            })
        else:
            return None
