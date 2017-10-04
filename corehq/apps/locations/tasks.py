import uuid
from dimagi.utils.couch.database import iter_docs
from corehq.util.couch import IterDB, iter_update, DocUpdate
from corehq.util.decorators import serial_task
from corehq.apps.commtrack.models import StockState, sync_supply_point
from corehq.apps.locations.models import SQLLocation
from corehq.apps.es.users import UserES
from corehq.apps.users.forms import generate_strong_password
from corehq.apps.users.models import CommCareUser
from corehq.apps.users.util import format_username


@serial_task("{location_type.domain}-{location_type.pk}",
             default_retry_delay=30, max_retries=3)
def sync_administrative_status(location_type, sync_supply_points=True):
    """Updates supply points of locations of this type"""
    if sync_supply_points:
        for location in SQLLocation.objects.filter(location_type=location_type):
            # Saving the location should be sufficient for it to pick up the
            # new supply point.  We'll need to save it anyways to store the new
            # supply_point_id.
            location.save()
    if location_type.administrative:
        _hide_stock_states(location_type)
    else:
        _unhide_stock_states(location_type)


def _hide_stock_states(location_type):
    (StockState.objects
     .filter(sql_location__location_type=location_type)
     .update(sql_location=None))


def _unhide_stock_states(location_type):
    for location in SQLLocation.objects.filter(location_type=location_type):
        (StockState.objects
         .filter(case_id=location.supply_point_id)
         .update(sql_location=location))


@serial_task("{domain}", default_retry_delay=30, max_retries=3)
def sync_supply_points(location_type):
    for location in SQLLocation.objects.filter(location_type=location_type):
        sync_supply_point(location)
        location.save()


# TODO add message on types page
@serial_task("{location_type.domain}-{location_type.pk}",
             default_retry_delay=30, max_retries=0)
def update_location_users(location_type):
    """
    Called when location_type.has_user is changed.
    Updates existing locations of that type to create or archive the
    corresponding users.
    """
    if location_type.has_user:
        _create_or_unarchive_users(location_type)
    else:
        _archive_users(location_type)


def _get_users_by_loc_id(location_type):
    """Find any existing users previously assigned to this type"""
    loc_ids = SQLLocation.objects.filter(location_type=location_type).location_ids()
    user_ids = list(UserES()
                    .domain(location_type.domain)
                    .show_inactive()
                    .term('user_location_id', list(loc_ids))
                    .values_list('_id', flat=True))
    return {
        user_doc['user_location_id']: CommCareUser.wrap(user_doc)
        for user_doc in iter_docs(CommCareUser.get_db(), user_ids)
        if 'user_location_id' in user_doc
    }


def _get_unique_username(domain, base, suffix=0, tries_left=3):
    if tries_left == 0:
        raise AssertionError("Username {} on domain {} exists in multiple variations, "
                             "what's up with that?".format(base, domain))
    with_suffix = "{}{}".format(base, suffix) if suffix else base
    username = format_username(with_suffix, domain)
    if not CommCareUser.username_exists(username):
        return username
    return _get_unique_username(domain, base, suffix + 1, tries_left - 1)


def make_location_user(location):
    """For locations where location_type.has_user is True"""
    return CommCareUser.create(
        location.domain,
        _get_unique_username(location.domain, location.site_code),
        generate_strong_password(),  # They'll need to reset this anyways
        uuid=uuid.uuid4().hex,
        commit=False,
    )


def _create_or_unarchive_users(location_type):
    users_by_loc = _get_users_by_loc_id(location_type)

    with IterDB(CommCareUser.get_db()) as iter_db:
        for loc in SQLLocation.objects.filter(location_type=location_type):
            user = users_by_loc.get(loc.location_id, None) or make_location_user(loc)
            user.is_active = True
            user.user_location_id = loc.location_id
            user.set_location(loc, commit=False)
            iter_db.save(user)
            loc.user_id = user._id
            loc.save()


def _archive_users(location_type):

    def archive(user_doc):
        if user_doc['is_active']:
            user_doc['is_active'] = False
            return DocUpdate(user_doc)

    user_ids = (SQLLocation.objects
                .filter(location_type=location_type)
                .values_list('user_id', flat=True))
    iter_update(CommCareUser.get_db(), archive, user_ids)

    for loc in SQLLocation.objects.filter(location_type=location_type):
        loc.user_id = ''
        loc.save()
