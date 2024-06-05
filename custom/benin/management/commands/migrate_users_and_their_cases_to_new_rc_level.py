from django.core.management.base import BaseCommand

from corehq.apps.locations.models import SQLLocation
from corehq.apps.users.user_data import prime_user_data_caches

LOCATION_TYPE_VILLAGE = "Village"
LOCATION_TYPE_RC = "RC"


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
                    4. Update users location to corresponding RC location
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
                            _update_cases(user=user, current_owner_id=village.location_id,
                                          new_owner_id=new_user_rc_location.location_id)
                            _update_users_location(user=user, location=new_user_rc_location)
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
    users = _find_users_at_location(location)
    prime_user_data_caches(users, domain)

    return [
        user
        for user in users
        if user.user_data.get('usertype') == 'rc'
    ]


def _find_users_at_location(location):
    # ToDo: return users at location
    return []


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


def _update_cases(user, current_owner_id, new_owner_id):
    cases = _find_cases(owner_id=current_owner_id, opened_by_user_id=user.user_id)
    log("fUpdating {len(cases)} cases for user {user.username}")
    # ToDo: update cases with progress bar
    return cases


def log(message):
    # ToDo: add logging to log message where ever needed
    pass


def _find_cases(owner_id, opened_by_user_id):
    # ToDo: find open cases owned and opened by specific user
    return []


def _update_users_location(user, location):
    # ToDo: update user's primary location
    pass


class MultipleMatchingLocationsFound(Exception):
    pass
