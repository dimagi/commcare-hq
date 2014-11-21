from celery.schedules import crontab
from celery.task import periodic_task
from custom.dhis2.models import JsonApiRequest, JsonApiError, Dhis2OrgUnit
from django.conf import settings


@periodic_task(run_every=crontab(minute=3, hour=3))  # Run daily at 03h03
def sync_org_units():
    """
    Synchronize DHIS2 Organization Units with local data
    """
    request = JsonApiRequest(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    try:
        __, json = request.get('organisationUnits', params={'paging': 'false', 'links': 'false'})
    except JsonApiError:
        # TODO: Task failed. Try again later
        raise
    their_org_units = {ou['id']: ou for ou in json['organisationUnits']}
    our_org_units = {ou.id_: ou for ou in Dhis2OrgUnit.objects.all()}
    # Add new org units
    for id_, ou in their_org_units.iteritems():
        if id_ not in our_org_units:
            org_unit = Dhis2OrgUnit(id_=id_, name=ou['name'])
            org_unit.save()
    # Delete former org units
    for id_ in our_org_units:
        if id_ not in their_org_units:
            org_unit = Dhis2OrgUnit.objects.get(id_)
            org_unit.delete()


def push_child_entities():
    """
    Register child entities in DHIS2 and enroll them in the Pediatric
    Nutrition Assessment and Underlying Risk Assessment programs.
    """
    # TODO: Set cchq_case_id
    pass


def pull_child_entities():
    """
    Create new child cases for nutrition tracking in CommCare.
    """
    # TODO: Add custom field dhis2_organization_unit_id
    pass


@periodic_task(run_every=crontab(minute=4, hour=4))  # Run daily at 04h04
def sync_child_entities():
    """
    Create new child cases for nutrition tracking in CommCare or associate
    already-registered child cases with DHIS2 child entities.
    """
    pass


def send_nutrition_data():
    """
    Send received nutrition data to DHIS2.
    """
    pass
