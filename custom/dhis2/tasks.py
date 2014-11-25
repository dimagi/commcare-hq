from celery.schedules import crontab
from celery.task import periodic_task
from custom.dhis2.models import JsonApiRequest, JsonApiError, Dhis2OrgUnit, dhis2_entities_to_dicts, Dhis2ApiQueryError
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


def push_child_entities(children):
    """
    Register child entities in DHIS2 and enroll them in the Pediatric
    Nutrition Assessment and Underlying Risk Assessment programs.
    """
    # TODO: Set cchq_case_id in DHIS2
    # TODO: Set dhis2_organization_unit_id in CCHQ
    pass


def pull_child_entities(children):
    """
    Create new child cases for nutrition tracking in CommCare.
    """
    # TODO: Add custom field dhis2_organization_unit_id
    # TODO: Set cchq_case_id in DHIS2
    pass


def get_top_org_unit():
    """
    Return the top-most organisation unit.

    We expect this to be a country.
    """
    # TODO: Is there a better way to do this?
    request = JsonApiRequest(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    __, org_units_json = request.get('organisationUnits', params={'links': 'false'})
    org_unit = org_units_json['organisationUnits'][0]
    while True:
        __, org_unit = request.get('organisationUnits/' + org_unit['id'])
        if 'parent' not in org_unit:
            break
    return org_unit


def get_resource_id(resource, name):
    """
    Returns the ID of the given resource type with the given name
    """
    request = JsonApiRequest(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    __, json = request.get(resource, params={'links': 'false', 'query': name})
    if not json[resource]:
        return None
    if len(json[resource]) > 1:
        raise Dhis2ApiQueryError('Query returned multiple results')
    return json[resource][0]['id']


def get_entity_id(name):
    """
    Returns the ID of the given entity type
    """
    return get_resource_id('trackedEntities', name)


def get_te_attr_id(name):
    """
    Returns the ID of the given tracked entity attribute
    """
    return get_resource_id('trackedEntityAttributes', name)


def get_children_only_theirs():
    """
    Returns a list of child entities that don't have cchq_case_id set
    """
    top = get_top_org_unit()
    child_entity = get_entity_id('Person')  # TODO: 'Child'
    cchq_case_id = get_te_attr_id('cchq_case_id')  # TODO: 'CCHQ Case ID'?
    # NOTE: Because we don't have an "UNSET" filter, we will need to iterate all, and append the unset ones to a list
    request = JsonApiRequest(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    __, json = request.get(
        'trackedEntityInstances',
        params={
            'paging': 'false', 'links': 'false',
            'trackedEntity': child_entity,
            'ou': top['id'],
            'ouMode': 'DESCENDANTS',
            'attribute': cchq_case_id + ':UNSET'  # cchq_case_id  # TODO: ":UNSET"?!
        })
    return dhis2_entities_to_dicts(json)


def get_children_only_ours():
    """
    Returns a list of new child cases which don't have dhis2_organization_unit_id set
    """
    pass


@periodic_task(run_every=crontab(minute=4, hour=4))  # Run daily at 04h04
def sync_child_entities():
    """
    Create new child cases for nutrition tracking in CommCare or associate
    already-registered child cases with DHIS2 child entities.
    """
    children = get_children_only_theirs()
    pull_child_entities(children)

    children = get_children_only_ours()
    push_child_entities(children)


def send_nutrition_data():
    """
    Send received nutrition data to DHIS2.
    """
    pass
