import datetime
from collections import defaultdict
import pytz
from xml.etree import ElementTree

from celery.task import periodic_task
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils.dateparse import parse_datetime, parse_date

from casexml.apps.case.mock import CaseBlock
from corehq import toggles
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.soft_assert import soft_assert
from dimagi.utils.decorators.memoized import memoized

from .case_utils import CASE_TYPE_EPISODE
from .const import (
    DOSE_TAKEN_INDICATORS,
    DAILY_SCHEDULE_FIXTURE_NAME,
    DAILY_SCHEDULE_ID,
    SCHEDULE_ID_FIXTURE,
    HISTORICAL_CLOSURE_REASON,
)
from .exceptions import EnikshayTaskException
from .data_store import AdherenceDatastore

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
        self.adherence_data_store = AdherenceDatastore(domain)

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
                logger.error(
                    "Error calculating adherence values for episode case_id({}): {}".format(
                        episode.case_id,
                        e
                    )
                )

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
        self._cache_dose_taken_by_date = False

    @memoized
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
        # Returns list of 'adherence' cases of which 'adherence_value' is one of DOSE_KNOWN_INDICATORS
        return self.case_updater.adherence_data_store.dose_known_adherences(
            self.episode.case_id
        )

    def get_latest_adherence_date(self):
        """
        return open case of type 'adherence' reverse-indexed to episode that
            has the latest 'adherence_date' property of all
        """
        return self.case_updater.adherence_data_store.latest_adherence_date(
            self.episode.case_id
        )

    def calculate_doses_taken_by_day(self, adherence_cases):
        """
        Args:
            adherence_cases: list of 'adherence' case dicts

        Returns:
            dict indexed by date part of 'adherence_date' and whether a dose is taken as value.
            Below is criteria to calculate whether a dose is taken on a day or not

        If there are multiple cases on one day filter to a single case as per below
        1. Find most relevant case
            if only non-enikshay source cases
                consider the case with latest_modified - irrespective of case is closed/open

            if only enikshay source cases
                filter by '(closed and closure_reason == HISTORICAL_CLOSURE_REASON) or open'
                consider the case with latest modified after above filter

            if mix of enikshay and non-enikshay source cases
                ignore non-enikshay and apply above enikshay only condition
        2. Check if 'adherence_value' of most relevent case is one of DOSE_TAKEN_INDICATORS
        """
        def is_dose_taken(cases):
            # runs above discribed calculation and returns whether a dose is taken or not
            sources = set(map(lambda x: x["adherence_source"], cases))
            if 'enikshay' not in sources:
                valid_cases = cases
            else:
                valid_cases = filter(
                    lambda case: (
                        case['adherence_source'] is 'enikshay' and
                        (not case['closed'] or (case['closed'] and
                         case['adherence_closure_reason'] == HISTORICAL_CLOSURE_REASON))
                    ),
                    cases
                )
            if valid_cases:
                by_modified_on = sorted(valid_cases, key=lambda case: case['modified_on'])
                return by_modified_on[-1]['adherence_value'] in DOSE_TAKEN_INDICATORS
            else:
                return False

        # index by 'adherence_date'
        cases_by_date = defaultdict(list)
        for case in adherence_cases:
            adherence_date = parse_date(case['adherence_date']) or parse_datetime(case['adherence_date']).date()
            cases_by_date[adherence_date].append(case)

        # calculate whether adherence is taken on each day
        dose_taken_by_date = defaultdict(bool)
        for d, cases in cases_by_date.iteritems():
            dose_taken_by_date[d] = is_dose_taken(cases)

        return dose_taken_by_date

    def get_adherence_schedule_start_date(self):
        # return property 'adherence_schedule_date_start' of episode case, cast to datetime
        raw_date = self.get_property('adherence_schedule_date_start')
        if not raw_date:
            return None
        if parse_datetime(raw_date):
            return parse_datetime(raw_date)
        elif parse_date(raw_date):
            return datetime.datetime.combine(parse_date(raw_date), datetime.datetime.min.time())
        else:
            raise EnikshayTaskException(
                "Episode case {case_id} has invalid format for 'adherence_schedule_date_start' {date}".format(
                    case_id=self.episode.case_id,
                    date=raw_date
                )
            )
            return None

    def count_doses_taken(self, dose_taken_by_date, lte=None, gte=None):
        """
        Args:
            dose_taken_by_date: result of self.calculate_doses_taken_by_day
        Returns:
            total count of adherence_cases excluding duplicates on a given day. If there are
            two adherence_cases on one day at different time, it will be counted as one
        """
        if bool(lte) != bool(gte):
            raise EnikshayTaskException("Both of lte and gte should be specified or niether of them")

        if not lte:
            return dose_taken_by_date.values().count(True)
        else:
            # any efficient way to do this - numpy, python bisect?
            return [
                is_taken
                for date, is_taken in dose_taken_by_date.iteritems()
                if lte.date() <= date <= gte.date()
            ].count(True)

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

        debug_data = []
        adherence_schedule_date_start = self.get_adherence_schedule_start_date()
        debug_data.append("adherence_schedule_date_start: {}".format(adherence_schedule_date_start))
        debug_data.append("purge_date: {}".format(self.case_updater.purge_date))

        if not adherence_schedule_date_start:
            # adherence schedule hasn't been selected, so no update necessary
            return {'update': {}, 'debug_data': debug_data}

        default_update = {
            'aggregated_score_date_calculated': adherence_schedule_date_start - datetime.timedelta(days=1),
            'expected_doses_taken': 0,
            'aggregated_score_count_taken': 0,
            'adherence_total_doses_taken': 0,
            'adherence_latest_date_recorded': adherence_schedule_date_start - datetime.timedelta(days=1)
        }

        if adherence_schedule_date_start > self.case_updater.purge_date:
            update = default_update
        else:
            update = {}
            latest_adherence_date = self.get_latest_adherence_date()
            debug_data.append("latest_adherence_date: {}".format(latest_adherence_date))
            if not latest_adherence_date:
                update = default_update
            else:
                update["adherence_latest_date_recorded"] = latest_adherence_date
                if latest_adherence_date < self.case_updater.purge_date:
                    update["aggregated_score_date_calculated"] = latest_adherence_date
                else:
                    update["aggregated_score_date_calculated"] = self.case_updater.purge_date

                # calculate 'adherence_total_doses_taken'
                adherence_cases = self.get_valid_adherence_cases()
                dose_taken_by_date = self.calculate_doses_taken_by_day(adherence_cases)
                update["adherence_total_doses_taken"] = self.count_doses_taken(dose_taken_by_date)
                # calculate 'aggregated_score_count_taken'
                update["aggregated_score_count_taken"] = self.count_doses_taken(
                    dose_taken_by_date,
                    lte=adherence_schedule_date_start,
                    gte=update["aggregated_score_date_calculated"]
                )

                # calculate 'expected_doses_taken' score
                dose_data = self.case_updater.get_doses_data()
                adherence_schedule_id = self.get_property('adherence_schedule_id') or DAILY_SCHEDULE_ID
                doses_per_week = dose_data.get(adherence_schedule_id)
                if doses_per_week:
                    update['expected_doses_taken'] = int(((
                        (update['aggregated_score_date_calculated'] - adherence_schedule_date_start)).days / 7.0
                    ) * doses_per_week)
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
        return {'update': update, 'debug_data': debug_data}

    def case_block(self):
        """
        Returns:
            CaseBlock object with adherence updates. If no update is necessary, None is returned
        """
        update = self.update_json()['update']
        if update:
            return CaseBlock(**{
                'case_id': self.episode.case_id,
                'create': False,
                'update': update
            })
        else:
            return None
