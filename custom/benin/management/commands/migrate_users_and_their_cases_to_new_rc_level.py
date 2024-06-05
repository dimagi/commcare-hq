import datetime
import math

from django.core.management.base import BaseCommand

from casexml.apps.case.mock import CaseBlock
from dimagi.utils.chunked import chunked

from corehq.apps.es.cases import CaseES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.dbaccessors import get_users_by_location_id
from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.user_data import prime_user_data_caches
from corehq.util.log import with_progress_bar

LOCATION_TYPE_VILLAGE = "Village"
LOCATION_TYPE_RC = "RC"


logfile = f"migrate_users_and_their_cases_to_new_rc_level_{datetime.datetime.utcnow()}"


class Command(BaseCommand):
    help = 'Migrate benin project\'s users and their cases to new rc level locations'

    def add_arguments(self, parser):
        super(Command, self).add_arguments(parser)

        parser.add_argument('domain')
        parser.add_argument(
            '--dry_run',
            action='store_true',
            default=False,
            help="A dry run to only share the updates that would happen",
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
        villages = _find_locations(domain=domain, location_type_code=LOCATION_TYPE_VILLAGE)
        for village in villages:
            users = _find_rc_users_at_location(domain, village)
            for user in users:
                user_rc_number = user.user_data.get('rc_number')
                if user_rc_number:
                    try:
                        new_user_rc_location = _find_child_location_with_name(
                            parent_location=village,
                            location_name=user_rc_number
                        )
                    except MultipleMatchingLocationsFound:
                        log(f"Multiple matching locations found for user {user.username}:{user.user_id} "
                            f"with rc number {user_rc_number}")
                    else:
                        if new_user_rc_location:
                            _update_cases(domain=domain, user=user, current_owner_id=village.location_id,
                                          new_owner_id=new_user_rc_location.location_id)
                            _update_users_location(user=user, location=new_user_rc_location)
                            log(f"User {user.username}:{user.user_id} updates completed.")
                        else:
                            log(f"User {user.username}:{user.user_id} rc {user_rc_number} location not found ")
                else:
                    log(f"User {user.username}:{user.user_id} missing rc number")


def _find_locations(domain, location_type_code):
    return SQLLocation.active_objects.filter(
        domain=domain,
        location_type__code=location_type_code
    )


def _find_rc_users_at_location(domain, location):
    # return users with usertype as 'rc'
    users = _find_users_at_location(domain, location)
    prime_user_data_caches(users, domain)

    return [
        user
        for user in users
        if user.user_data.get('usertype') == 'rc'
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


def _update_cases(domain, user, current_owner_id, new_owner_id):
    case_ids = _find_case_ids(owner_id=current_owner_id, opened_by_user_id=user.user_id)

    log("fUpdating {len(case_ids)} cases for user {user.username}")

    for case_ids in with_progress_bar(
        chunked(case_ids, 100),
        length=math.ceil(len(case_ids) / 100),
        oneline=False
    ):
        _update_case_owners(domain, case_ids, new_owner_id)


def _update_case_owners(domain, case_ids, owner_id):
    case_blocks = []
    for case_id in case_ids:
        case_blocks.append(
            CaseBlock(
                create=False,
                case_id=case_id,
                owner_id=owner_id
            )
        )
    submit_case_blocks(
        case_blocks=case_blocks,
        domain=domain,
        device_id=__name__ + ".migrate_users_and_their_cases_to_new_rc_level"
    )


def log(message):
    print(message)
    with open(logfile, 'w+') as filestream:
        filestream.write(message)


def _find_case_ids(owner_id, opened_by_user_id):
    # find ids for open cases owned and opened by specific user
    return (
        CaseES()
        .owner(owner_id)
        .opened_by(opened_by_user_id)
        .is_closed(False)
        .get_ids()
    )


def _update_users_location(user, location):
    user.set_location(location)


class MultipleMatchingLocationsFound(Exception):
    pass
