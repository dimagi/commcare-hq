import math
import time
import logging

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.es.cases import CaseES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.user_data import prime_user_data_caches
from corehq.util.log import with_progress_bar
from custom.benin.tasks import process_updates_for_village_async

LOCATION_TYPE_VILLAGE = "village"
LOCATION_TYPE_RC = "rc"

logger = logging.getLogger("custom_benin_script")


class Command(BaseCommand):
    help = 'Migrate benin project\'s users and their cases to new rc level locations'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('domain')
        parser.add_argument(
            '--village_id'
        )
        parser.add_argument(
            '--commune_id'
        )
        parser.add_argument(
            '--dry_run',
            action='store_true',
            default=False,
            help="A dry run to only share the updates that would happen",
        )
        parser.add_argument(
            '--run_in_celery',
            action='store_true',
            default=False,
            help="Will spawn a celery task for each village",
        )

    def handle(self, domain, **options):
        """
        Steps:
        1. Fetch all villages (location type: Village).
        2. For each village:
            1. Fetch all users assigned to the village with usertype 'rc'
            2. For each user
                1. find the corresponding RC under the village with name same as user's user data in rc_number.
                   Log error if no matching RC, and move to next user
                2. if RC present
                    1. Find all OPEN cases (case_type: menage, membre)
                        1. owned by village
                        2. opened_by the user (Use CaseES.opened_by)
                    2. Find all OPEN cases (case_type: seance_educative, fiche_pointage)
                        1. opened_by the user (Use CaseES.opened_by)
                        2. Why are we updating it though? They are already owned by users. They aren't many though
                    3. Update all cases
                        1. Update owner to be the corresponding RC location
                    4. Update users location to corresponding RC location only after cases to enable
                       retry on this update in case of any intermittent failures
        """
        dry_run = options['dry_run']
        village_id = options['village_id']
        commune_id = options['commune_id']
        run_in_celery = options['run_in_celery']

        assert not village_id and commune_id, "Provide either village ID or commune ID, cannot use both"

        start_time = time.time()
        logger.info("Started processing of script")
        if village_id:
            villages = SQLLocation.active_objects.get_locations([village_id])
        elif commune_id:
            villages = _find_child_locations(
                domain=domain,
                location_id=commune_id,
                location_type_code=LOCATION_TYPE_VILLAGE
            )
        else:
            villages = _find_locations(domain=domain, location_type_code=LOCATION_TYPE_VILLAGE)
        logger.info(f"Total number of villages found: {len(villages)}")

        for village in villages:
            if run_in_celery:
                process_updates_for_village_async.delay(domain, village.id, dry_run)
            else:
                process_updates_for_village(domain, village.id, dry_run)

        if run_in_celery:
            logger.info("Celery tasks queued for all villages.")
        else:
            logger.info(f"Processing completed. Total execution time: {(time.time() - start_time):.2f}s")


def process_updates_for_village(domain, village_id, dry_run):
    village = SQLLocation.active_objects.get(pk=village_id)
    logger.info(f"Starting updates for village {village.name}")
    users = _find_rc_users_at_location(domain, village)
    logger.info(f"Total number of users in village {village.name}: {len(users)}")
    for user in users:
        user_rc_number = user.get_user_data(domain).get('rc_number')
        user_user_type = user.get_user_data(domain).get('usertype')
        user_stats_str = ' '.join([
            'Active' if user.is_active else 'Deactivated',
            user_rc_number if user_rc_number else 'RC:None',
            user_user_type if user_user_type else 'Type:None'
        ])
        if user_rc_number:
            try:
                new_user_rc_location = _find_child_location_with_name(
                    parent_location=village,
                    location_name=user_rc_number
                )
            except MultipleMatchingLocationsFound:
                logger.error(f"[{user_stats_str}] Multiple matching locations found for user "
                             f"{user.username}:{user.user_id} with rc number {user_rc_number}")
            else:
                if new_user_rc_location:
                    _update_cases(domain=domain, user=user, current_owner_id=village.location_id,
                                  new_owner_id=new_user_rc_location.location_id,
                                  dry_run=dry_run)
                    _update_users_location(user=user, existing_location=village,
                                           new_location=new_user_rc_location, dry_run=dry_run)
                    logger.info(f"[{user_stats_str}] User {user.username}:{user.user_id} updates completed.")
                else:
                    logger.error(f"[{user_stats_str}] User {user.username}:{user.user_id} rc "
                                 f"{user_rc_number} location not found")
        else:
            logger.error(f"[{user_stats_str}] User {user.username}:{user.user_id} missing rc number")
    logger.info(f"Updates for village {village.name} processed.")


def _find_locations(domain, location_type_code):
    return SQLLocation.active_objects.filter(
        domain=domain,
        location_type__code=location_type_code
    )

def _find_child_locations(domain, location_id, location_type_code):
    loc = SQLLocation.active_objects.get(domain=domain, location_id=location_id)
    return loc.get_descendants().filter(location_type__code=location_type_code)

def _find_rc_users_at_location(domain, location):
    # return users with usertype as 'rc'
    users = _find_users_at_location(domain, location)
    users = prime_user_data_caches(users, domain)

    return [
        user
        for user in users
        if user.get_user_data(domain).get('usertype') == 'rc'
    ]


def _find_users_at_location(domain, location):
    return get_users_by_location_id(domain, location.location_id)


def _find_child_location_with_name(parent_location, location_name):
    # find location under parent location that has the name location_name
    locations = parent_location.get_descendants().filter(
        name=location_name
    )
    if not locations:
        return None
    if len(locations) == 1:
        return locations[0]
    if len(locations) > 1:
        raise MultipleMatchingLocationsFound


def _update_cases(domain, user, current_owner_id, new_owner_id, dry_run):
    case_types = ['menage', 'membre', 'seance_educative', 'fiche_pointage']
    for case_type in case_types:
        case_ids = _find_case_ids(case_type=case_type, owner_id=current_owner_id, opened_by_user_id=user.user_id)

        logger.info(f"Updating {len(case_ids)} {case_type} cases for user {user.username}")
        if case_ids:
            for case_ids in with_progress_bar(
                chunked(case_ids, 100),
                length=math.ceil(len(case_ids) / 100),
                oneline=False
            ):
                _update_case_owners(domain, case_ids, new_owner_id, dry_run)


def _update_case_owners(domain, case_ids, owner_id, dry_run):
    case_blocks = []
    for case_id in case_ids:
        case_blocks.append(
            CaseBlock(
                create=False,
                case_id=case_id,
                owner_id=owner_id
            ).as_text()
        )
    if not dry_run:
        submit_case_blocks(
            case_blocks=case_blocks,
            domain=domain,
            device_id=__name__
        )


def _find_case_ids(case_type, owner_id, opened_by_user_id):
    # find ids for open cases of a case type owned and opened by specific user
    return (
        CaseES()
        .case_type(case_type)
        .owner(owner_id)
        .opened_by(opened_by_user_id)
        .is_closed(False)
        .get_ids()
    )


def _update_users_location(user, existing_location, new_location, dry_run):
    if not dry_run:
        user.set_location(new_location)
        user.unset_location_by_id(existing_location.location_id)
    logger.info(f"User {user.username}:{user.user_id} location updated to {new_location.location_id}")


class MultipleMatchingLocationsFound(Exception):
    pass
