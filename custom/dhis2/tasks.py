"""
Celery tasks used by the World Vision Sri Lanka Nutrition project
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
from corehq.apps.es import CaseES, FormES, UserES
from corehq.apps.hqcase.utils import submit_case_blocks, get_case_by_identifier
from corehq.apps.users.models import CommCareUser
from couchforms.models import XFormInstance
from custom.dhis2.models import Dhis2Api, Dhis2OrgUnit


# TODO: Move to init
DOMAIN = 'wv-lanka'
DATA_ELEMENT_NAMES = {
    # CCHQ field names : DHIS2 data element names

    # DHIS2 Program: Paediatric Nutrition Assessment
    # CCHQ Case Type: child_gmp
    'child_first_name': 'First Name',
    'child_hh_name': 'Last Name',
    'dob': 'Date of Birth',
    'child_gender': 'Gender',
    # '?': 'CHDR Number',
    'mother_first_name': 'Name of Mother/Guardian',
    'mother_phone_number': 'Mobile Number of Mother',
    'street_name': 'Address',

    # DHIS2 Event: Nutrition Assessment
    # CCHQ Form: Growth Monitoring
    'date_of_visit': 'Event Date',
    'child_age_months': 'Age at Follow Up Visit (months)',
    'child_height_rounded': 'Height (cm)',
    'child_weight': 'Weight (kg)',
    'bmi': 'Body Mass Index',

    # DHIS2 Program: Underlying Risk Assessment
    # CCHQ Case Type: child_gmp
    'mother_id': 'Household Number',
    # 'mother_first_name': 'Name of Mother/Guardian',
    # '?': 'GN Division of Household',

    # DHIS2 Event: Underlying Risk Assessment
    # CCHQ Form: ?
    # '': '',
}


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


def push_child_entities(children):
    """
    Register child entities in DHIS2 and enroll them in the Pediatric
    Nutrition Assessment and Underlying Risk Assessment programs.

    :param children: A generator of cases that include a properties named
                     dhis2_organization_unit_id.

    .. Note:: Once pushed, external_id is set to the ID of the
              tracked entity instance.

    This fulfills the second requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    nutrition_id = dhis2_api.get_program_id('Pediatric Nutrition Assessment')
    # if not nutrition_id:
    #     # DHIS2 has not been configured for this project
    #     raise Dhis2ConfigurationError('DHIS2 program "Pediatric Nutrition Assessment" not found')
    risk_id = dhis2_api.get_program_id('Underlying Risk Assessment')
    # if not risk_id:
    #     # DHIS2 has not been configured for this project
    #     raise Dhis2ConfigurationError('DHIS2 program "Underlying Risk Assessment" not found')
    today = date.today().strftime('%Y-%m-%d')  # More explicit than str(date.today())
    for child in children:
        ou_id = child['dhis2_organisation_unit_id']  # App sets this case property from user custom data

        try:
            # Search for cchq_case_id in case previous attempt to register failed.
            dhis2_child = next(dhis2_api.gen_instances_with_equals('Child', 'cchq_case_id', child['_id']))
            dhis2_child_id = dhis2_child['Identity']
        except StopIteration:
            # Register child entity in DHIS2, and set cchq_case_id.
            dhis2_child = {
                'cchq_case_id': child['_id'],

                'Name': child['name'],
                'Height': child['child_height'],
                'Weight': child['child_weight'],  # ?
                'Age at time of visit': child['age'],  # ?
                'Body-mass index': child['bmi'],  # ?
                # Spec gives these as program event attributes, but they seem more
                # like tracked entity instance attributes than event attributes.
                # TODO: Check
                'First Name': child['child_first_name'],
                'Last Name': child['last_name'],  # ?
                'Date of Birth': child['dob'],
                'Gender': child['child_gender'],
                'Name of Mother/Guardian': child['mother_first_name'],
                'Mobile Number of the Mother': child['mother_phone_number'],
                'Address': ', '.join((child['street_name'],
                                     child['village'],
                                     child['district'],
                                     child['province']))
            }
            result = dhis2_api.add_te_inst(dhis2_child, 'Child', ou_id=ou_id)
            # TODO: What does result look like?
            dhis2_child_id = result['Identity']

        # Enroll in Pediatric Nutrition Assessment
        event_data = {
            # Spec gives these as program event attributes, but they seem more
            # like tracked entity instance attributes than event attributes.
            # TODO: Check
            'First Name': child['child_first_name'],
            'Last Name': child['last_name'],  # ?
            'Date of Birth': child['dob'],
            'Gender': child['child_gender'],
            'Name of Mother/Guardian': child['mother_first_name'],
            'Mobile Number of the Mother': child['mother_phone_number'],
            'Address': ', '.join((child['street_name'],
                                 child['village'],
                                 child['district'],
                                 child['province']))
        }
        dhis2_api.enroll_in_id(dhis2_child_id, nutrition_id, today, event_data)

        # Enroll in Underlying Risk Assessment
        if is_at_risk(child):
            dhis2_api.enroll_in_id(dhis2_child_id, risk_id, today)

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


def is_at_risk(child):
    """
    Determines whether a child should be enrolled in the Underlying Risk
    Assessment program
    """
    # TODO: Criteria TBD
    return True  # For the sake of testing


def pull_child_entities(domain, dhis2_children):
    """
    Create new child cases for nutrition tracking in CommCare.

    Sets external_id on new child cases, and cchq_case_id on DHIS2
    tracked entity instances. (cchq_case_id is initially unset because the
    case is new and does not exist in CommCare.)

    :param domain: The domain/project of the application
    :param dhis2_children: A list of dictionaries of Child tracked entities
                           from the DHIS2 API where cchq_case_id is unset

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
        dhis2_child['cchq_case_id'] = case_id
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


def get_case_by_external_id(domain, id_):
    """
    Filter cases by external_id
    """
    return get_case_by_identifier(domain, id_)


def get_children_only_theirs():
    """
    Returns a list of child entities that don't have cchq_case_id set
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    return dhis2_api.gen_instances_with_unset('Child', 'cchq_case_id')


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
def sync_child_entities():
    """
    Create new child cases for nutrition tracking in CommCare or associate
    already-registered child cases with DHIS2 child entities.
    """
    children = get_children_only_theirs()
    pull_child_entities(DOMAIN, children)

    children = gen_children_only_ours(DOMAIN)
    push_child_entities(children)


@periodic_task(run_every=crontab(minute=5, hour=5))  # Run daily at 05h05
def send_nutrition_data():
    """
    Send received nutrition data to DHIS2.

    This fulfills the fourth requirement of `DHIS2 Integration`_


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx

    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    nutrition_id = dhis2_api.get_program_id('Pediatric Nutrition Assessment')
    xforms = []
    events = {'eventList': []}
    for xform in gen_unprocessed_growth_monitoring_forms():
        xforms.append(xform)
        event = dhis2_api.form_to_event(nutrition_id, xform, DATA_ELEMENT_NAMES)
        events['eventList'].append(event)
    dhis2_api.send_events(events)
    mark_as_processed(xforms)


def gen_unprocessed_growth_monitoring_forms():
    query = FormES().domain(DOMAIN).filter({
        # dhis2_te_inst_id indicates that the case has been enrolled in both
        # programs by push_child_entities()
        'not': {'or': [{'missing': {'field': 'form.dhis2_te_inst_id'}},
                       {'term': {'form.dhis2_te_inst_id': ''}}]}
    }).filter({
        # and it must not have been processed before
        'or': [{'missing': {'field': 'form.dhis2_processed'}},
               {'term': {'form.dhis2_processed': ''}}]
    })
    result = query.run()
    if result.total:
        for doc in result.hits:
            yield XFormInstance.wrap(doc)


def mark_as_processed(forms):
    for form in forms:
        form.form['dhis2_processed'] = True
        form.save()
