from datetime import date
from apps.case.models import CommCareCase
from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.es.cases import CaseES
from custom.dhis2.models import Dhis2Api, Dhis2OrgUnit, JsonApiRequest, JsonApiError
from django.conf import settings


DOMAIN = 'barproject'


# TODO: Handle timeouts gracefully


@periodic_task(run_every=crontab(minute=3, hour=3))  # Run daily at 03h03
def sync_org_units():
    """
    Synchronize DHIS2 Organization Units with local data.

    This data is used to fulfill the first requirement of
    `DHIS2 Integration`_: Allow mobile users in CommCareHQ to be
    associated with a particular DHIS2 Organisation Unit, so that when
    they create cases their new cases can be associated with that area
    or facility.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    request = JsonApiRequest(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    try:
        __, json = request.get('organisationUnits', params={'paging': 'false', 'links': 'false'})
    except JsonApiError as err:
        # TODO: Task failed. Try again later IF RECOVERABLE
        # http://celery.readthedocs.org/en/latest/userguide/tasks.html#retrying
        # raise self.retry(exc=err)
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

    :param children: A generator of cases that have properties named
                     dhis2_organization_unit_id and dhis2_te_inst_id.

    .. Note:: Once pushed, dhis2_te_inst_id is set to the ID of the
              tracked entity instance.

    This fulfills the second requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    nutrition_id = dhis2_api.get_resource_id('program', 'Pediatric Nutrition Assessment')
    risk_id = dhis2_api.get_resource_id('program', 'Underlying Risk Assessment')
    today = date.today().strftime('%Y-%m-%d')  # More explicit than str(date.today())
    for child in children:
        ou_id = child['dhis2_organization_unit_id']  # App sets this case property from user custom data

        try:
            # Search for cchq_case_id in case previous attempt to register failed.
            dhis2_child = next(dhis2_api.gen_instances_with_equals('Child', 'cchq_case_id', child['_id']))
        except StopIteration:
            # Register child entity in DHIS2, and set cchq_case_id.
            dhis2_child = {
                'cchq_case_id': child['_id'],
                # TODO: And the rest of the attributes
                # These are hard-coded for the World Vision project, but
                # should be configurable if we make the DHIS2 API client more
                # generic
                'Name': child['name'],
                'Date of Birth': child['dob'],
                'Favourite Colour': child['favorite_color'],  # <-- TODO: Not really. Determine attributes.
            }
            result = dhis2_api.add_te_inst(dhis2_child, 'Child', ou_id=ou_id)
            # TODO: What does result look like?
            dhis2_child = result

        # Enroll in Pediatric Nutrition Assessment
        dhis2_api.enroll_in_id(dhis2_child, nutrition_id, today)

        # Enroll in Underlying Risk Assessment
        dhis2_api.enroll_in_id(dhis2_child, risk_id, today)

        # TODO: Set dhis2_te_inst_id in CCHQ to flag the case as pushed.
        child['dhis2_te_inst_id'] = dhis2_child['id']
        # TODO: Use case block, e.g.
        # casexml = ElementTree.tostring(caseblock.as_xml())
        # submit_case_blocks(casexml, domain.name)


def pull_child_entities(domain, children):
    """
    Create new child cases for nutrition tracking in CommCare.

    Sets dhis2_te_inst_id on new child cases, and cchq_case_id on DHIS2
    tracked entity instances. (cchq_case_id is initially unset because the
    case is new and does not exist in CommCare.)

    :param domain: The domain/project of the application
    :param children: A list of dictionaries of Child tracked entities
                     from the DHIS2 API where cchq_case_id is unset

    This fulfills the third requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    # TODO: ...
    pass


def get_children_only_theirs():
    """
    Returns a list of child entities that don't have cchq_case_id set
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    return dhis2_api.gen_instances_with_unset('Child', 'cchq_case_id')  # TODO: Or would that be 'CCHQ Case ID'?


def gen_children_only_ours(domain):
    """
    Returns a list of new child cases which don't have dhis2_organization_unit_id set
    """
    # Fetch cases where dhis2_organisation_unit_id is set and dhis2_te_inst_id is empty

    # query = CaseES().domain(domain).filter({
    #     # dhis2_organisation_unit_id is not empty
    #     'not': {
    #         'or': [
    #             {'dhis2_organisation_unit_id': None},
    #             {'dhis2_organisation_unit_id': ''}
    #         ]
    #     }
    # }).filter({
    #     # dhis2_te_inst_id is empty
    #     'or': [
    #         {'dhis2_te_inst_id': None},
    #         {'dhis2_te_inst_id': ''}
    #     ]
    # })

    # query = CaseES().domain(domain).filter({
    #     # dhis2_organisation_unit_id is not empty
    #     'not': {'dhis2_organisation_unit_id': ''}
    # }).filter({
    #     # dhis2_te_inst_id is empty
    #     'dhis2_te_inst_id': ''
    # })

    query = CaseES().domain(DOMAIN).filter({'missing': {'field': 'dhis2_organization_unit_id'}})
    result = query.run()
    # return result.hits if result.total else []
    if result.total:
        for doc in result.hits:
            yield CommCareCase.wrap(doc)


@periodic_task(run_every=crontab(minute=4, hour=4))  # Run daily at 04h04
def sync_child_entities():
    """
    Create new child cases for nutrition tracking in CommCare or associate
    already-registered child cases with DHIS2 child entities.
    """
    children = get_children_only_theirs()
    pull_child_entities(DOMAIN, children)

    children = gen_children_only_ours(DOMAIN)
    push_child_entities(children)


def send_nutrition_data():
    """
    Send received nutrition data to DHIS2.
    """
    # TODO: ...
    pass
