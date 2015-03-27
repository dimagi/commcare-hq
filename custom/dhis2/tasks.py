"""
Celery tasks used by the World Vision Sri Lanka Nutrition project

Two tasks are executed daily:

  * sync_org_units: Synchronize DHIS2 Organization Units with local data

  * sync_child_entities: Create new child cases in CommCare for nutrition
    tracking, and associate CommCare child cases with DHIS2 child entities
    and enroll them in the Pediatric Nutrition Assessment and Underlying Risk
    Assessment programs.

Creating program events for Nutrition Assessment and Risk Assessment programs
is done using FormRepeater payload generators. See payload_generators.py for
details.

"""
from datetime import date, timedelta
import logging
import uuid
from xml.etree import ElementTree
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.es import CaseES, UserES
from corehq.apps.hqcase.utils import submit_case_blocks, get_case_by_identifier
from corehq.apps.users.models import CommCareUser
from custom.dhis2.const import CCHQ_CASE_ID, NUTRITION_ASSESSMENT_PROGRAM_FIELDS, ORG_UNIT_FIXTURES, CASE_TYPE, \
    TRACKED_ENTITY, CASE_NAME
from custom.dhis2.models import Dhis2Api, Dhis2OrgUnit, Dhis2Settings, FixtureManager, JsonApiError, \
    Dhis2ApiQueryError


logger = logging.getLogger(__name__)


def push_case(case, dhis2_api):
    """
    Create a DHIS2 tracked entity instance from the form's case and enroll in
    the nutrition assessment programme.
    """
    if getattr(case, 'dhis_org_id', None):
        ou_id = case.dhis_org_id  # App sets this case property from user custom data
    else:
        # This is an old case, or org unit is not set. Skip it
        return

    program_data = {dhis2_attr: case[cchq_attr]
                    for cchq_attr, dhis2_attr in NUTRITION_ASSESSMENT_PROGRAM_FIELDS.iteritems()
                    if getattr(case, cchq_attr, None)}
    if 'Gender' in program_data:
        # Gender is an optionSet. Options are "Male", "Female" and "Undefined"
        # cf. http://dhis1.internal.commcarehq.org:8080/dhis/api/optionSets/wG0c8ReYyNz.json
        program_data['Gender'] = program_data['Gender'].capitalize()  # "male" -> "Male"
    else:
        program_data['Gender'] = 'Undefined'

    try:
        # Search for CCHQ Case ID in case previous attempt to register failed.
        instance = next(dhis2_api.gen_instances_with_equals(TRACKED_ENTITY, CCHQ_CASE_ID, case['_id']))
        instance_id = instance['Instance']
    except StopIteration:
        # Create a DHIS2 tracked entity instance
        instance = {CCHQ_CASE_ID: case['_id']}
        instance.update(program_data)
        try:
            instance_id = dhis2_api.add_te_inst(TRACKED_ENTITY, ou_id, instance)
        except (JsonApiError, Dhis2ApiQueryError) as err:
            logger.error('Failed to create DHIS2 entity from CCHQ case "%s". DHIS2 server error: %s',
                         case['_id'], err)
            return

    # Enroll in Pediatric Nutrition Assessment
    date_of_visit = case['date_of_visit'] if getattr(case, 'date_of_visit', None) else date.today()
    try:
        response = dhis2_api.enroll_in(instance_id, 'Paediatric Nutrition Assessment', date_of_visit, program_data)
    except (JsonApiError, Dhis2ApiQueryError) as err:
        logger.error('Failed to push CCHQ case "%s" to DHIS2 program "%s". DHIS2 server error: %s',
                     case['_id'], 'Paediatric Nutrition Assessment', err)
        return
    if response['status'] != 'SUCCESS':
        logger.error('Failed to push CCHQ case "%s" to DHIS2 program "%s". DHIS2 API error: %s',
                     case['_id'], 'Paediatric Nutrition Assessment', response)
        return

    # Set external_id in CCHQ to flag the case as pushed.
    update_case_external_id(case, instance_id)


def push_child_entities(settings, children):
    """
    Register child entities in DHIS2 and enroll them in the Pediatric
    Nutrition Assessment program.

    :param children: child_gmp cases where external_id is not set

    .. Note:: Once pushed, external_id is set to the ID of the
              tracked entity instance.

    This fulfills the second requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    dhis2_api = Dhis2Api(settings.dhis2['host'], settings.dhis2['username'], settings.dhis2['password'],
                         settings.dhis2['top_org_unit_name'])
    # nutrition_id = dhis2_api.get_program_stage_id('Nutrition Assessment')
    for child in children:
        push_case(child, dhis2_api)


def pull_child_entities(settings, dhis2_children):
    """
    Create new child cases for nutrition tracking in CommCare.

    Sets external_id on new child cases, and CCHQ Case ID on DHIS2
    tracked entity instances. (CCHQ Case ID is initially unset because the
    case is new and does not exist in CommCare.)

    :param settings: DHIS2 settings, incl. relevant domain
    :param dhis2_children: A list of dictionaries of TRACKED_ENTITY (i.e.
                           "Child") tracked entities from the DHIS2 API where
                           CCHQ Case ID is unset

    This fulfills the third requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    dhis2_api = Dhis2Api(settings.dhis2['host'], settings.dhis2['username'], settings.dhis2['password'],
                         settings.dhis2['top_org_unit_name'])
    for dhis2_child in dhis2_children:
        # Add each child separately. Although this is slower, it avoids problems if a DHIS2 API call fails
        # ("Instance" is DHIS2's friendly name for "id")
        logger.info('DHIS2: Syncing DHIS2 child "%s"', dhis2_child['Instance'])
        case = get_case_by_identifier(settings.domain, dhis2_child['Instance'])  # Get case by external_id
        if case:
            case_id = case['case_id']
        else:
            user = get_user_by_org_unit(settings.domain, dhis2_child['Org unit'],
                                        settings.dhis2['top_org_unit_name'])
            if not user:
                # No user is assigned to this or any higher organisation unit
                logger.error('DHIS2: Unable to import DHIS2 instance "%s"; there is no user at org unit "%s" or '
                             'above to assign the case to.', dhis2_child['Instance'], dhis2_child['Org unit'])
                continue
            case_id = create_case_from_dhis2(dhis2_child, settings.domain, user)
        dhis2_child[CCHQ_CASE_ID] = case_id
        dhis2_api.update_te_inst(dhis2_child)


def get_user_by_org_unit(domain, org_unit_id, top_org_unit_name):
    """
    Look up user ID by a DHIS2 organisation unit ID
    """
    result = (UserES()
              .domain(domain)
              .mobile_users()
              # .term('user_data.dhis_org_id', org_unit_id)
              .run())
    # cf. http://www.elasticsearch.org/guide/en/elasticsearch/reference/current/mapping-dynamic-mapping.html
    # If/when we upgrade elasticsearch, we can filter on dynamic mappings and
    # uncomment the ".term" line above. Until then, check it ourselves ...
    for doc in result.hits:
        if doc['user_data'].get('dhis_org_id') == org_unit_id:
            return CommCareUser.wrap(doc)
    # No user is assigned to this organisation unit (i.e. region or facility).
    # Try its parent org unit.
    Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, domain, ORG_UNIT_FIXTURES)
    org_units = {ou.id: ou for ou in Dhis2OrgUnit.objects.all()}
    if (
        org_unit_id in org_units and
        org_units[org_unit_id].name != top_org_unit_name and
        org_units[org_unit_id].parent_id
    ):
        return get_user_by_org_unit(domain, org_units[org_unit_id].parent_id, top_org_unit_name)
    # We don't know that org unit ID, or we're at the top for this project, or we're at the top of DHIS2
    return None


def create_case_from_dhis2(dhis2_child, domain, user):
    """
    Create a new case using the data pulled from DHIS2

    :param dhis2_child: TRACKED_ENTITY (i.e. "Child") from DHIS2
    :param domain: (str) The name of the domain
    :param user: (Document) The owner of the new case
    :return: New case ID
    """
    case_id = uuid.uuid4().hex
    update = {k: dhis2_child[v] for k, v in NUTRITION_ASSESSMENT_PROGRAM_FIELDS.iteritems()}
    update['dhis_org_id'] = dhis2_child['Org unit']
    # Do the inverse of push_case() to 'Gender' / 'child_gender'
    if 'child_gender' in update:
        if update['child_gender'] == 'Undefined':
            del update['child_gender']
        else:
            update['child_gender'] = update['child_gender'].lower()
    caseblock = CaseBlock(
        create=True,
        case_id=case_id,
        owner_id=user.userID,
        user_id=user.userID,
        version=V2,
        case_type=CASE_TYPE,
        case_name=update[CASE_NAME] if CASE_NAME else '',
        external_id=dhis2_child['Instance'],
        update=update
    )
    casexml = ElementTree.tostring(caseblock.as_xml())
    submit_case_blocks(casexml, domain)
    return case_id


def update_case_external_id(case, external_id):
    """
    Update the external_id of a case
    """
    caseblock = CaseBlock(
        create=False,
        case_id=case['_id'],
        version=V2,
        external_id=external_id
    )
    casexml = ElementTree.tostring(caseblock.as_xml())
    submit_case_blocks(casexml, case['domain'])


def get_children_only_theirs(settings):
    """
    Returns a list of child entities that are enrolled in Paediatric Nutrition
    Assessment and don't have CCHQ Case ID set.
    """
    dhis2_api = Dhis2Api(settings.dhis2['host'], settings.dhis2['username'], settings.dhis2['password'],
                         settings.dhis2['top_org_unit_name'])
    for inst in dhis2_api.gen_instances_in_program('Paediatric Nutrition Assessment'):
        if not inst.get(CCHQ_CASE_ID):
            yield inst


def gen_children_only_ours(domain):
    """
    Returns a list of child_gmp cases where external_id is not set
    """
    result = (CaseES()
              .domain(domain)
              .case_type(CASE_TYPE)
              .empty('external_id')
              .run())
    if result.total:
        for doc in result.hits:
            yield CommCareCase.wrap(doc)


# Check for new cases on DHIS2 every 6 hours
@periodic_task(run_every=timedelta(hours=6), queue='background_queue')
def fetch_cases():
    """
    Import new child cases from DHIS2 for nutrition tracking
    """
    for settings in Dhis2Settings.all_enabled():
        logger.info('DHIS2: Fetching cases for domain "%s" from "%s"', settings.domain, settings.dhis2['host'])
        children = get_children_only_theirs(settings)
        pull_child_entities(settings, children)


# There is a large number of org units, but the lookup table is not deployed to handsets.
@periodic_task(run_every=crontab(minute=3, hour=3), queue='background_queue')
def fetch_org_units():
    """
    Synchronize DHIS2 Organization Units with local data.

    This data is used to fulfill the first requirement of
    `DHIS2 Integration`_: Allow mobile users in CommCareHQ to be
    associated with a particular DHIS2 Organisation Unit, so that when
    they create cases their new cases can be associated with that area
    or facility.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx

    """
    for settings in Dhis2Settings.all_enabled():
        logger.info('DHIS2: Fetching org units for domain "%s" with "%s"', settings.domain, settings.dhis2['host'])
        dhis2_api = Dhis2Api(settings.dhis2['host'], settings.dhis2['username'], settings.dhis2['password'],
                             settings.dhis2['top_org_unit_name'])
        Dhis2OrgUnit.objects = FixtureManager(Dhis2OrgUnit, settings.domain, ORG_UNIT_FIXTURES)
        our_org_units = {ou.id: ou for ou in Dhis2OrgUnit.objects.all()}
        their_org_units = {}
        # Add new org units
        for ou in dhis2_api.gen_org_units():
            their_org_units[ou['id']] = ou
            if ou['id'] not in our_org_units:
                logger.info('DHIS2: Adding org unit "%s"', ou['name'])
                org_unit = Dhis2OrgUnit(id=ou['id'], name=ou['name'],
                                        parent_id=dhis2_api.get_org_unit_parent_id(ou['id']))
                org_unit.save()
        # Delete former org units
        for id_, ou in our_org_units.iteritems():
            if id_ not in their_org_units:
                logger.info('DHIS2: Deleting org unit "%s"', ou.name)
                ou.delete()
