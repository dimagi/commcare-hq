from datetime import datetime
from celery.schedules import crontab
from celery.task import periodic_task
from custom.dhis2.models import Dhis2OrgUnit
from django.conf import settings
import requests


class JsonApiError(Exception):
    pass


class JsonApiRequest(object):
    """
    Wrap requests with URL, header and authentication for DHIS2 API

    Return HTTP status, JSON
    """

    def __init__(self, host, username, password):
        self.baseurl = host + '/api/'
        self.header = {'Accept': 'application/json'}
        self.auth = (username, password)

    @staticmethod
    def json_or_error(response):
        if not 200 <= response.status_code < 300:
            raise JsonApiError('API request failed with HTTP status %s: %s' %
                               (response.status_code, response.text))
        return response.status_code, response.json()

    def get(self, path, **kwargs):
        try:
            response = requests.get(self.baseurl + path, header=self.header, auth=self.auth, **kwargs)
        except Exception as err:  # TODO: What exception?! (socket error; authentication error; ...?)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)

    def post(self, path, data, **kwargs):
        try:
            response = requests.post(self.baseurl + path, data, header=self.header, auth=self.auth, **kwargs)
        except Exception as err:  # TODO: What exception?! (socket error; authentication error; ...?)
            raise JsonApiError(str(err))
        return JsonApiRequest.json_or_error(response)


@periodic_task(run_every=crontab(minute=3, hour=3))  # Run daily at 03h03
def sync_org_units():
    """
    Synchronize DHIS2 Organization Units with local data
    """
    request = JsonApiRequest(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    try:
        __, json = request.get('organisationUnits', params={'paging': 'false', 'links': 'false'})
    except JsonApiError:
        # TODO: Task failed. Try again, or abort
        raise
    their_org_units = {ou['id']: ou for ou in json['organisationUnits']}
    our_org_units = do_some_magic_here()  # Dict keyed on ID
    # Add new org units
    for id_ in their_org_units:
        if id_ not in our_org_units:
            last_updated = datetime.strptime(their_org_units[id_]['lastUpdated'], '%Y-%m-%dT%H:%M:%S.%f+0000') \
                if their_org_units[id_].get('lastUpdated') \
                else None
            # TODO: Get details
            # TODO: Assert parent
            # TODO: Add parent if necessary, recurse.
            ou = Dhis2OrgUnit(
                dhis2_id=id_,
                name=their_org_units[id_]['name'],
                created=datetime.strptime(their_org_units[id_]['created'], '%Y-%m-%dT%H:%M:%S.%f+0000'),
                last_updated=last_updated,
                code=their_org_units[id_]['code'])
            ou.save()
        # TODO: Sync other details, esp parent/children
    for id_ in our_org_units:
        if id_ not in their_org_units:
            ou = Dhis2OrgUnit.objects.get(id_)
            ou.delete()  # TODO: Safely


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
