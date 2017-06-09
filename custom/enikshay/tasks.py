import datetime
from collections import defaultdict
import pytz

from celery.task import periodic_task
from celery.schedules import crontab
from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils.dateparse import parse_datetime, parse_date

from corehq import toggles
from corehq.apps.hqcase.utils import update_case
from corehq.apps.fixtures.models import FixtureDataItem
from corehq.form_processor.interfaces.dbaccessors import CaseAccessors
from corehq.util.soft_assert import soft_assert
from dimagi.utils.decorators.memoized import memoized

from custom.enikshay.exceptions import ENikshayCaseNotFound
from .case_utils import CASE_TYPE_EPISODE, get_prescription_vouchers_from_episode, get_prescription_from_voucher
from .const import (
    DOSE_TAKEN_INDICATORS,
    DAILY_SCHEDULE_FIXTURE_NAME,
    DAILY_SCHEDULE_ID,
    SCHEDULE_ID_FIXTURE,
    HISTORICAL_CLOSURE_REASON,
    ENIKSHAY_TIMEZONE,
)
from .exceptions import EnikshayTaskException
from .data_store import AdherenceDatastore

logger = get_task_logger(__name__)


@periodic_task(
    run_every=crontab(hour=0, minute=0),  # every day at midnight
    queue=getattr(settings, 'CELERY_PERIODIC_QUEUE', 'celery')
)
def enikshay_task():
    # runs adherence and voucher calculations for all domains that have
    # `toggles.UATBC_ADHERENCE_TASK` enabled
    domains = toggles.UATBC_ADHERENCE_TASK.get_enabled_domains()
    for domain in domains:
        updater = EpisodeUpdater(domain)
        updater.run()


class Timer:
    def __enter__(self):
        self.start = datetime.datetime.now()
        return self

    def __exit__(self, *args):
        self.end = datetime.datetime.now()
        self.interval = (self.end - self.start).seconds


class EpisodeUpdater(object):
    """
    This iterates over all open 'episode' cases and sets 'adherence' and 'voucher' related properties
    This is applicable to various enikshay domains. The domain can be specified in __init__ method
    """

    def __init__(self, domain):
        self.domain = domain
        # set purge_date to 30 days back
        self.purge_date = datetime.datetime.now(
            pytz.timezone(ENIKSHAY_TIMEZONE)).date() - datetime.timedelta(days=30)
        self.date_today_in_india = datetime.datetime.now(pytz.timezone(ENIKSHAY_TIMEZONE)).date()
        self.adherence_data_store = AdherenceDatastore(domain)

    def run(self):
        # iterate over all open 'episode' cases and set 'adherence' properties
        update_count = 0
        noupdate_count = 0
        error_count = 0
        with Timer() as t:
            for episode in self._get_open_episode_cases():
                adherence_update = EpisodeAdherenceUpdate(episode, self)
                voucher_update = EpisodeVoucherUpdate(self.domain, episode)
                try:
                    update_json = adherence_update.update_json()
                    update_json.update(voucher_update.update_json())
                    if update_json:
                        update_case(self.domain, episode.case_id, update_json)
                        update_count += 1
                    else:
                        noupdate_count += 1
                except Exception, e:
                    error_count += 1
                    logger.error(
                        "Error calculating updates for episode case_id({}): {}".format(
                            episode.case_id,
                            e
                        )
                    )
        logger.info(
            "Summary of enikshay_task: domain: {domain}, duration (sec): {duration} "
            "Cases Updated {updates}, cases errored {errors} and {noupdates} "
            "cases didn't need update. ".format(
                domain=self.domain, duration=t.interval, updates=update_count, errors=error_count,
                noupdates=noupdate_count)
        )

    def update_single_case(self, episode_case):
        # updates a single episode_case.
        assert episode_case.domain == self.domain
        update_json = EpisodeAdherenceUpdate(episode_case, self).update_json()
        if update_json:
            update_case(self.domain, episode_case.case_id, update_json)

    def _get_open_episode_cases(self):
        # return all open 'episode' cases
        case_accessor = CaseAccessors(self.domain)
        case_ids = case_accessor.get_open_case_ids_in_domain_by_type(CASE_TYPE_EPISODE)
        return case_accessor.iter_cases(case_ids)

    @memoized
    def get_doses_data(self):
        # return 'doses_per_week' by 'schedule_id' from the Fixture data
        fixtures = FixtureDataItem.get_item_list(self.domain, DAILY_SCHEDULE_FIXTURE_NAME)
        doses_per_week_by_schedule_id = {}
        for f in fixtures:
            schedule_id = f.fields[SCHEDULE_ID_FIXTURE].field_list[0].field_value
            doses_per_week = int(f.fields["doses_per_week"].field_list[0].field_value)
            doses_per_week_by_schedule_id[schedule_id] = doses_per_week
        return doses_per_week_by_schedule_id


class EpisodeAdherenceUpdate(object):
    """
    Class to capture adherence related calculations specific to an 'episode' case
    per the spec https://docs.google.com/document/d/1FjSdLYOYUCRBuW3aSxvu3Z5kvcN6JKbpDFDToCgead8/edit
    """
    def __init__(self, episode_case, case_updater):
        """
        Args:
            episode_case: An 'episode' case object
            case_updater: EpisodeUpdater object
        """
        self.episode = episode_case
        self.case_updater = case_updater
        self._cache_dose_taken_by_date = False

    @property
    @memoized
    def case_properties(self):
        return self.episode.dynamic_case_properties()

    def get_property(self, property):
        """
        Args:
            name of the case-property

        Returns:
            value of the episode case-property named 'property'
        """
        return self.case_properties.get(property)

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

    @staticmethod
    def calculate_doses_taken_by_day(adherence_cases):
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
                        case.get('adherence_source') == 'enikshay' and
                        (not case['closed'] or (case['closed'] and
                         case.get('adherence_closure_reason') == HISTORICAL_CLOSURE_REASON))
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
        # return property 'adherence_schedule_date_start' of episode case (is expected to be a date object)
        raw_date = self.get_property('adherence_schedule_date_start')
        if not raw_date:
            return None
        elif parse_date(raw_date):
            return parse_date(raw_date)
        else:
            raise EnikshayTaskException(
                "Episode case {case_id} has invalid format for 'adherence_schedule_date_start' {date}".format(
                    case_id=self.episode.case_id,
                    date=raw_date
                )
            )
            return None

    @staticmethod
    def count_doses_taken(dose_taken_by_date, start_date=None, end_date=None):
        """
        Args:
            dose_taken_by_date: result of self.calculate_doses_taken_by_day
        Returns:
            total count of adherence_cases excluding duplicates on a given day. If there are
            two adherence_cases on one day at different time, it will be counted as one
        """
        if bool(start_date) != bool(end_date):
            raise EnikshayTaskException("Both of start_date and end_date should be specified or niether of them")

        if not start_date:
            return dose_taken_by_date.values().count(True)
        else:
            # any efficient way to do this - numpy, python bisect?
            return [
                is_taken
                for date, is_taken in dose_taken_by_date.iteritems()
                if start_date <= date <= end_date
            ].count(True)

    def update_json(self):
        debug_data = []
        adherence_schedule_date_start = self.get_adherence_schedule_start_date()
        debug_data.append("adherence_schedule_date_start: {}".format(adherence_schedule_date_start))
        debug_data.append("purge_date: {}".format(self.case_updater.purge_date))

        if not adherence_schedule_date_start:
            # adherence schedule hasn't been selected, so no update necessary
            return {}

        latest_adherence_date = self.get_latest_adherence_date()
        debug_data.append("latest_adherence_date: {}".format(latest_adherence_date))

        if (adherence_schedule_date_start > self.case_updater.purge_date) or not latest_adherence_date:
            return self.check_and_return({
                'aggregated_score_date_calculated': adherence_schedule_date_start - datetime.timedelta(days=1),
                'expected_doses_taken': 0,
                'aggregated_score_count_taken': 0,
                'adherence_total_doses_taken': 0,
                'adherence_latest_date_recorded': adherence_schedule_date_start - datetime.timedelta(days=1),
                'one_week_score_count_taken': 0,
                'two_week_score_count_taken': 0,
                'month_score_count_taken': 0,
                'one_week_adherence_score': 0,
                'two_week_adherence_score': 0,
                'month_adherence_score': 0,
            })

        adherence_cases = self.get_valid_adherence_cases()
        dose_taken_by_date = self.calculate_doses_taken_by_day(adherence_cases)
        update = self.get_aggregated_scores(
            latest_adherence_date, adherence_schedule_date_start, dose_taken_by_date)
        update.update(self.get_adherence_scores(dose_taken_by_date))

        return self.check_and_return(update)

    def get_adherence_scores(self, doses_taken_by_date):
        today = self.case_updater.date_today_in_india
        start_date = self.get_adherence_schedule_start_date()

        if today - datetime.timedelta(days=7) >= start_date:
            one_week_score_count_taken = self.count_doses_taken(
                doses_taken_by_date,
                start_date=today - datetime.timedelta(days=7),
                end_date=today,
            )
        else:
            one_week_score_count_taken = 0

        if today - datetime.timedelta(days=14) >= start_date:
            two_week_score_count_taken = self.count_doses_taken(
                doses_taken_by_date,
                start_date=today - datetime.timedelta(days=14),
                end_date=today,
            )
        else:
            two_week_score_count_taken = 0

        if today - datetime.timedelta(days=30) >= start_date:
            month_score_count_taken = self.count_doses_taken(
                doses_taken_by_date,
                start_date=today - datetime.timedelta(days=30),
                end_date=today,
            )
        else:
            month_score_count_taken = 0

        return {
            'one_week_score_count_taken': one_week_score_count_taken,
            'two_week_score_count_taken': two_week_score_count_taken,
            'month_score_count_taken': month_score_count_taken,
            'one_week_adherence_score': round((one_week_score_count_taken / 7.0) * 100, 2),
            'two_week_adherence_score': round((two_week_score_count_taken / 14.0) * 100, 2),
            'month_adherence_score': round((month_score_count_taken / 30.0) * 100, 2),
        }

    def get_aggregated_scores(self, latest_adherence_date, adherence_schedule_date_start, dose_taken_by_date):
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
        update = {}

        update["adherence_latest_date_recorded"] = latest_adherence_date
        if latest_adherence_date < self.case_updater.purge_date:
            update["aggregated_score_date_calculated"] = latest_adherence_date
        else:
            update["aggregated_score_date_calculated"] = self.case_updater.purge_date

        # calculate 'adherence_total_doses_taken'
        update["adherence_total_doses_taken"] = self.count_doses_taken(dose_taken_by_date)
        # calculate 'aggregated_score_count_taken'
        update["aggregated_score_count_taken"] = self.count_doses_taken(
            dose_taken_by_date,
            start_date=adherence_schedule_date_start,
            end_date=update["aggregated_score_date_calculated"]
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

        return update

    def check_and_return(self, update_dict):
        """
        Args:
            update_dict: dict of case property name to values

        Returns:
            Checks if any one of update_dict is not set on self.episode case,
                if any of them are not returns update_dict after formatting any
                date values to string.
                If all of them are set as expected, returns None
        """
        needs_update = any([
            self.get_property(k) != v
            for (k, v) in update_dict.iteritems()
        ])
        if needs_update:
            # cast any date objects to strings, so that Django template rendering
            # used by update_case formats dates as YYYY:MM:DD instead of (Month Date, Year)
            return {key: str(val) if isinstance(val, datetime.date) else val
                    for key, val in update_dict.iteritems()}
        else:
            return None


class EpisodeVoucherUpdate(object):
    """
    Class to capture voucher related calculations specific to an 'episode' case
    """
    def __init__(self, domain, episode_case):
        """
        Args:
            episode_case: An 'episode' case object
        """
        self.domain = domain
        self.episode = episode_case

    @staticmethod
    def _get_fulfilled_voucher_date(voucher):
        return voucher.get_case_property('date_fulfilled')

    @memoized
    def _get_all_vouchers(self):
        return get_prescription_vouchers_from_episode(self.domain, self.episode.case_id)

    def _get_fulfilled_vouchers(self):
        relevant_vouchers = [
            voucher for voucher in self._get_all_vouchers()
            if (voucher.get_case_property('voucher_type') == 'prescription'
                and voucher.get_case_property('state') == 'fulfilled')
        ]
        return sorted(relevant_vouchers, key=self._get_fulfilled_voucher_date)

    def _get_fulfilled_available_vouchers(self):
        relevant_vouchers = [
            voucher for voucher in self._get_all_vouchers()
            if (voucher.get_case_property('voucher_type') == 'prescription'
                and voucher.get_case_property('state') in
                ['fulfilled', 'available', 'paid', 'approved', 'rejected'])
        ]
        return sorted(relevant_vouchers, key=lambda v: v.get_case_property('date_issued'))

    @staticmethod
    def _updated_fields(existing_properties, new_properties):
        updated_fields = {}
        for prop, value in new_properties.items():
            existing_value = unicode(existing_properties.get(prop, '--'))
            new_value = unicode(value) if value is not None else u""
            if existing_value != new_value:
                updated_fields[prop] = value
        return updated_fields

    def update_json(self):
        output_json = {}
        output_json.update(self.get_prescription_total_days())
        output_json.update(self.get_prescription_refill_due_dates())
        output_json.update(self.get_first_voucher_details())
        return self._updated_fields(self.episode.dynamic_case_properties(), output_json)

    def get_prescription_total_days(self):
        prescription_json = {}
        total_days = 0
        for voucher in self._get_fulfilled_vouchers():
            raw_days_value = voucher.get_case_property('final_prescription_num_days')
            total_days += int(raw_days_value) if raw_days_value else 0

            for num_days in (30, 60, 90, 120,):
                prop = "prescription_total_days_threshold_{}".format(num_days)
                if total_days >= num_days and prop not in prescription_json:
                    prescription_json[prop] = self._get_fulfilled_voucher_date(voucher)
        prescription_json['prescription_total_days'] = total_days

        return prescription_json

    def get_prescription_refill_due_dates(self):
        """The dates on which the app predicts that the episode should be eligible for prescription refills

        https://docs.google.com/document/d/1s1-MHKS5I8cvf0_7NvcqeTsYGsXLy9YGArw2L7cZSRM/edit#
        """
        fulfilled_available_vouchers = self._get_fulfilled_available_vouchers()
        if not fulfilled_available_vouchers:
            return {}

        latest_voucher = fulfilled_available_vouchers[-1]

        date_last_refill = parse_date(latest_voucher.get_case_property('date_issued'))
        if date_last_refill is None:
            return {}

        voucher_length = (
            latest_voucher.get_case_property('final_prescription_num_days')
            or latest_voucher.get_case_property('prescription_num_days')
        )

        try:
            refill_due_date = date_last_refill + datetime.timedelta(days=int(voucher_length))
        except (TypeError, ValueError):
            return {}

        return {
            'date_last_refill': date_last_refill.strftime("%Y-%m-%d"),
            'voucher_length': voucher_length,
            'refill_due_date': refill_due_date.strftime("%Y-%m-%d"),
        }

    def get_first_voucher_details(self):
        all_voucher_cases = sorted(self._get_all_vouchers(), key=lambda c: c.get_case_property('date_issued'))
        fulfilled_voucher_cases = sorted(
            self._get_fulfilled_vouchers(),
            key=lambda c: c.get_case_property('date_fulfilled')
        )

        try:
            first_voucher_generated = all_voucher_cases[0]
        except IndexError:
            return {}

        try:
            first_prescription = get_prescription_from_voucher(self.domain, first_voucher_generated.case_id)
        except ENikshayCaseNotFound:
            return {}

        return {
            'first_voucher_generation_date': first_voucher_generated.get_case_property('date_issued'),
            'first_voucher_drugs': first_prescription.get_case_property('drugs_ordered_readable'),
            'first_voucher_validation_date': (fulfilled_voucher_cases[0].get_case_property('date_fulfilled')
                                              if fulfilled_voucher_cases else '')
        }
