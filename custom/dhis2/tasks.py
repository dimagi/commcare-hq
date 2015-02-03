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
from datetime import date
import random
import uuid
from xml.etree import ElementTree
from django.conf import settings
from casexml.apps.case.mock import CaseBlock
from casexml.apps.case.models import CommCareCase
from casexml.apps.case.xml import V2
from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.es import CaseES, UserES
from corehq.apps.hqcase.utils import submit_case_blocks, get_case_by_identifier
from corehq.apps.users.models import CommCareUser
from custom.dhis2.models import Dhis2Api, Dhis2OrgUnit


# TODO: Move to custom app attributes
DOMAIN = 'wv-lanka'

PROGRAM_FIELDS = {
    # CCHQ child_gmp case attribute: DHIS2 program attribute
    'child_first_name': 'First Name',
    'child_hh_name': 'Last Name',
    'dob': 'Date of Birth',
    'child_gender': 'Gender',
    'chdr_number': 'CHDR Number',
    'mother_first_name': 'Name of Mother/Guardian',
    'mother_phone_number': 'Mobile Number of the Mother',
    'street_name': 'Address',
}

NUTRITION_ASSESSMENT_FIELDS = {
    # CCHQ form field: DHIS2 event attribute

    # DHIS2 Event: Nutrition Assessment
    # CCHQ Form: Growth Monitoring
    # CCHQ form XMLNS: http://openrosa.org/formdesigner/b6a45e8c03a6167acefcdb225ee671cbeb332a40
    '/data/date_of_visit': 'Event Date',
    '/data/child_age_months': 'Age at Follow Up Visit (months)',
    '/data/child_height_rounded': 'Height (cm)',
    '/data/child_weight': 'Weight (kg)',
    '/data/bmi': 'Body Mass Index',
}

RISK_ASSESSMENT_FIELDS = {
    # CCHQ form field: DHIS2 event attribute

    # DHIS2 Event: Underlying Risk
    # CCHQ form XMLNS: http://openrosa.org/formdesigner/39F09AD4-B770-491E-9255-C97B34BDD7FC Assessment
    '/data/mother_id': 'Household Number',
    '/data/mother_first_name': 'Name of Mother/Guardian',
    '/data/gn': 'GN Division of Household',
}


def push_child_entities(children):
    """
    Register child entities in DHIS2 and enroll them in the Pediatric
    Nutrition Assessment program.

    :param children: child_gmp cases where external_id is not set

    .. Note:: Once pushed, external_id is set to the ID of the
              tracked entity instance.

    This fulfills the second requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    # nutrition_id = dhis2_api.get_program_stage_id('Nutrition Assessment')
    nutrition_id = dhis2_api.get_program_id('Paediatric Nutrition Assessment')
    today = date.today().strftime('%Y-%m-%d')  # More explicit than str(date.today())
    for child in children:
        try:
            ou_id = child['dhis2_organisation_unit_id']  # App sets this case property from user custom data
        except AttributeError:
            # App failed to set this case property from user custom data
            # TODO: Tell someone.
            # TODO: Or assume top org unit. Or both.
            # Skip to the next case
            continue

        try:
            # Search for CCHQ Case ID in case previous attempt to register failed.
            dhis2_child = next(dhis2_api.gen_instances_with_equals('Child', 'CCHQ Case ID', child['_id']))
            dhis2_child_id = dhis2_child['Identity']
        except StopIteration:
            # Register child entity in DHIS2, and set CCHQ Case ID.
            dhis2_child = {
                'CCHQ Case ID': child['_id'],
            }
            dhis2_child_id = dhis2_api.add_te_inst(dhis2_child, 'Child', ou_id=ou_id)

        # Enroll in Pediatric Nutrition Assessment
        program_data = {dhis2_attr: child[cchq_attr] for cchq_attr, dhis2_attr in PROGRAM_FIELDS.iteritems()}
        dhis2_api.enroll_in_id(dhis2_child_id, nutrition_id, today, program_data)

        # Set external_id in CCHQ to flag the case as pushed.
        commcare_user = CommCareUser.get(child['owner_id'])
        caseblock = CaseBlock(
            create=False,
            case_id=child['_id'],
            version=V2,
            update={
                'external_id': dhis2_child_id,
            }
        )
        casexml = ElementTree.tostring(caseblock.as_xml())
        submit_case_blocks(casexml, commcare_user.project.name)


def pull_child_entities(domain, dhis2_children):
    """
    Create new child cases for nutrition tracking in CommCare.

    Sets external_id on new child cases, and CCHQ Case ID on DHIS2
    tracked entity instances. (CCHQ Case ID is initially unset because the
    case is new and does not exist in CommCare.)

    :param domain: The domain/project of the application
    :param dhis2_children: A list of dictionaries of Child tracked entities
                           from the DHIS2 API where CCHQ Case ID is unset

    This fulfills the third requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    for dhis2_child in dhis2_children:
        # Add each child separately. Although this is slower, it avoids problems if a DHIS2 API call fails
        case = get_case_by_external_id(domain, dhis2_child['Instance'])  # Instance is DHIS2's friendly name for id
        if case:
            case_id = case['case_id']
        else:
            user = get_user_by_org_unit(domain, dhis2_child['Org unit'])
            if not user:
                # No user is assigned to this organisation unit (i.e. region or facility). Now what?
                # TODO: Now what? Ascend to parent org unit?
                continue
            case_id = uuid.uuid4().hex
            caseblock = CaseBlock(
                create=True,
                case_id=case_id,
                owner_id=user.userID,
                user_id=user.userID,
                version=V2,
                case_type='child_gmp',  # TODO: Move to a constant / setting
                update={
                    'external_id': dhis2_child['Instance'],
                    'name': dhis2_child['Name'],
                    'height': dhis2_child['Height'],
                    'weight': dhis2_child['Weight'],
                    'age': dhis2_child['Age at time of visit'],
                    'bmi': dhis2_child['Body-mass index'],
                }
            )
            casexml = ElementTree.tostring(caseblock.as_xml())
            submit_case_blocks(casexml, domain)
        dhis2_child['CCHQ Case ID'] = case_id
        dhis2_api.update_te_inst(dhis2_child)


def get_user_by_org_unit(domain, org_unit):
    """
    Look up user ID by a DHIS2 organisation unit ID
    """
    result = (UserES()
              .domain(domain)
              .term('user_data.dhis2_org_unit_id', org_unit)
              .run())
    if result.total:
        # Don't just assign all cases to the first user
        i = random.randrange(result.total)
        return CommCareUser.wrap(result.hits[i])
    return None


def get_case_by_external_id(domain, external_id):
    """
    Filter cases by external_id
    """
    return get_case_by_identifier(domain, external_id)


def get_children_only_theirs():
    """
    Returns a list of child entities that are enrolled in Paediatric Nutrition
    Assessment and don't have CCHQ Case ID set.
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    for inst in dhis2_api.gen_instances_in_program('Paediatric Nutrition Assessment'):
        if not inst.get('CCHQ Case ID'):
            yield inst


def gen_children_only_ours(domain):
    """
    Returns a list of child_gmp cases where external_id is not set
    """
    result = (CaseES()
              .domain(domain)
              .case_type('child_gmp')
              .empty('external_id')
              .run())
    if result.total:
        for doc in result.hits:
            yield CommCareCase.wrap(doc)


@periodic_task(run_every=crontab(minute=4, hour=4))  # Run daily at 04h04
def sync_cases():
    """
    Create new child cases in CommCare for nutrition tracking, and associate
    CommCare child cases with DHIS2 child entities and enroll them in the
    Pediatric Nutrition Assessment and Underlying Risk Assessment programs.
    """
    if not settings.DHIS2_ENABLED:
        return
    children = get_children_only_theirs()
    pull_child_entities(DOMAIN, children)

    children = gen_children_only_ours(DOMAIN)
    push_child_entities(children)


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
    if not settings.DHIS2_ENABLED:
        return
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    # TODO: Is it a bad idea to read all org units into dictionaries and sync them ...
    their_org_units = {ou['id']: ou for ou in dhis2_api.gen_org_units()}
    # ... or should we rather just drop all ours and import all theirs every time?
    our_org_units = {ou.id: ou for ou in Dhis2OrgUnit.objects.all()}
    # Add new org units
    for id_, ou in their_org_units.iteritems():
        if id_ not in our_org_units:
            org_unit = Dhis2OrgUnit(id=id_, name=ou['name'])
            org_unit.save()
    # Delete former org units
    for id_, ou in our_org_units.iteritems():
        if id_ not in their_org_units:
            ou.delete()
