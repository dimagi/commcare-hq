import logging

from django.conf import settings

from dimagi.utils.couch.database import iter_docs
from dimagi.utils.logging import notify_exception
from soil import DownloadBase

from corehq.apps.celery import task
from corehq.apps.commtrack.models import close_supply_point_case
from corehq.apps.data_interfaces.models import LocationFilterDefinition
from corehq.apps.locations.bulk_management import (
    LocationUploadResult,
    new_locations_import,
)
from corehq.apps.locations.const import LOCK_LOCATIONS_TIMEOUT
from corehq.apps.locations.models import SQLLocation
from corehq.apps.locations.util import dump_locations
from corehq.apps.userreports.dbaccessors import get_datasources_for_domain
from corehq.apps.userreports.tasks import rebuild_indicators_in_place
from corehq.apps.users.models import CouchUser
from corehq.toggles import LOCATIONS_IN_UCR
from corehq.util.decorators import serial_task
from corehq.util.workbook_json.excel_importer import MultiExcelImporter


@serial_task("{location_type.domain}-{location_type.pk}",
             default_retry_delay=30, max_retries=3, serializer='pickle')
def sync_administrative_status(location_type):
    """Updates supply points of locations of this type"""
    for location in SQLLocation.objects.filter(location_type=location_type):
        # Saving the location should be sufficient for it to pick up the
        # new supply point.  We'll need to save it anyways to store the new
        # supply_point_id.
        location.save()


@task
def download_locations_async(domain, download_id, include_consumption,
                             headers_only, owner_id, root_location_ids=None, **kwargs):
    DownloadBase.set_progress(download_locations_async, 0, 100)
    dump_locations(domain, download_id,
                   include_consumption=include_consumption, owner_id=owner_id,
                   root_location_ids=root_location_ids,
                   headers_only=headers_only, task=download_locations_async, **kwargs)
    DownloadBase.set_progress(download_locations_async, 100, 100)


@serial_task('{domain}', default_retry_delay=5 * 60, timeout=LOCK_LOCATIONS_TIMEOUT, max_retries=12,
             queue=settings.CELERY_MAIN_QUEUE, ignore_result=False)
def import_locations_async(domain, file_ref_id, user_id):
    try:
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
    except Exception as e:
        notify_exception(None, message=str(e))
        results = LocationUploadResult()
        results.errors = [str(e)]
    return {
        'messages': {
            'messages': results.messages,
            'errors': results.errors,
            'warnings': results.warnings,
            'success': results.success,
        }
    }


@task
def update_users_at_locations(domain, location_ids, supply_point_ids, ancestor_ids):
    """
    Update location fixtures for users given locations
    """
    from dimagi.utils.couch.database import iter_docs

    from corehq.apps.fixtures.models import UserLookupTableType
    from corehq.apps.locations.dbaccessors import user_ids_at_locations
    from corehq.apps.users.models import (
        CouchUser,
        update_fixture_status_for_users,
    )

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
    update_fixture_status_for_users(user_ids, UserLookupTableType.LOCATION)


@task
def delete_locations_related_rules(location_ids):
    for location_definition in LocationFilterDefinition.objects.filter(location_id__in=location_ids):
        for criteria in location_definition.caserulecriteria_set.all():
            rule = criteria.rule
            rule.delete_criteria()
            rule.delete_actions()
            rule.delete()
        location_definition.delete()


def deactivate_users_at_location(location_id):
    from corehq.apps.locations.dbaccessors import mobile_user_ids_at_locations
    user_ids = mobile_user_ids_at_locations([location_id])
    for doc in iter_docs(CouchUser.get_db(), user_ids):
        user = CouchUser.wrap_correctly(doc)
        user.is_active = False
        user.save(spawn_task=True)
