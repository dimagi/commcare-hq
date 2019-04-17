from __future__ import absolute_import
from __future__ import unicode_literals
import logging
import uuid

from celery.task import task
from django.conf import settings

from dimagi.utils.couch.database import iter_docs

from soil import DownloadBase

from corehq.apps.locations.const import LOCK_LOCATIONS_TIMEOUT
from corehq.apps.locations.util import dump_locations
from corehq.apps.commtrack.models import (
    StockState, sync_supply_point, close_supply_point_case,
)
from corehq.apps.es.users import UserES
from corehq.apps.locations.bulk_management import new_locations_import
from corehq.apps.locations.models import SQLLocation
from corehq.apps.userreports.dbaccessors import get_datasources_for_domain
from corehq.apps.userreports.tasks import rebuild_indicators_in_place
from corehq.apps.users.forms import generate_strong_password
from corehq.apps.users.models import CommCareUser, CouchUser
from corehq.apps.users.util import format_username
from corehq.toggles import LOCATIONS_IN_UCR
from corehq.util.couch import IterDB, iter_update, DocUpdate
from corehq.util.decorators import serial_task
from corehq.util.workbook_json.excel_importer import MultiExcelImporter


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


@task(serializer='pickle')
def download_locations_async(domain, download_id, include_consumption, headers_only):
    DownloadBase.set_progress(download_locations_async, 0, 100)
    dump_locations(domain, download_id, include_consumption=include_consumption,
                   headers_only=headers_only, task=download_locations_async)
    DownloadBase.set_progress(download_locations_async, 100, 100)


@serial_task('{domain}', default_retry_delay=5 * 60, timeout=LOCK_LOCATIONS_TIMEOUT, max_retries=12,
             queue=settings.CELERY_MAIN_QUEUE, ignore_result=False)
def import_locations_async(domain, file_ref_id, user_id):
    importer = MultiExcelImporter(import_locations_async, file_ref_id)
    user = CouchUser.get_by_user_id(user_id)
    results = new_locations_import(domain, importer, user)
    importer.mark_complete()

    if LOCATIONS_IN_UCR.enabled(domain):
        # We must rebuild datasources once the location import is complete in
        # case child locations were not updated, but a parent location was.
        # For example if a state was updated, the county may reference the state
        # and need to have its row updated
        datasources = get_datasources_for_domain(domain, "Location", include_static=True)
        for datasource in datasources:
            rebuild_indicators_in_place.delay(
                datasource.get_id, initiated_by=user.username, source='import_locations'
            )

    if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        # Log results because they are not sent to the view when
        # CELERY_TASK_ALWAYS_EAGER is true
        logging.getLogger(__name__).info(
            "import_locations_async %s results: %s -> success=%s",
            file_ref_id,
            " ".join(
                "%s=%r" % (name, getattr(results, name))
                for name in ["messages", "warnings", "errors"]
                if getattr(results, name)
            ),
            results.success,
        )

    return {
        'messages': {
            'messages': results.messages,
            'errors': results.errors,
            'warnings': results.warnings,
            'success': results.success,
        }
    }


@task(serializer='pickle')
def update_users_at_locations(domain, location_ids, supply_point_ids, ancestor_ids):
    """
    Update location fixtures for users given locations
    """
    from corehq.apps.users.models import CouchUser, update_fixture_status_for_users
    from corehq.apps.locations.dbaccessors import user_ids_at_locations
    from corehq.apps.fixtures.models import UserFixtureType
    from dimagi.utils.couch.database import iter_docs

    # close supply point cases
    for supply_point_id in supply_point_ids:
        close_supply_point_case(domain, supply_point_id)

    # unassign users from locations
    unassign_user_ids = user_ids_at_locations(location_ids)
    for doc in iter_docs(CouchUser.get_db(), unassign_user_ids):
        user = CouchUser.wrap_correctly(doc)
        for location_id in location_ids:
            if location_id not in user.get_location_ids(domain):
                continue
            if user.is_web_user():
                user.unset_location_by_id(domain, location_id, fall_back_to_next=True)
            elif user.is_commcare_user():
                user.unset_location_by_id(location_id, fall_back_to_next=True)

    # update fixtures for users at ancestor locations
    user_ids = user_ids_at_locations(ancestor_ids)
    update_fixture_status_for_users(user_ids, UserFixtureType.LOCATION)
