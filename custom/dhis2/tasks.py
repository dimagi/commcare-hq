"""
These are the Celery tasks used by the World Vision Sri Lanka Nutrition project

They assume the following data is available in CommCare and DHIS2.

Participating CommCare users need the following custom user property:

* dhis2_organization_unit_id: The organisation unit ID where the user is
  working. (In DHIS2 this can be a country, region or facility)

Required CommCare case attributes:

1. dhis2_organization_unit_id: The organisation unit ID of the owner of the
   case.
2. dhis2_te_inst_id: The ID of the DHIS2 tracked entity instance that
   corresponds with this case.

CommCare child growth monitoring forms must include:

* height
* weight
* mobile-calculated BMI
* age at time of visit
* hidden value "dhis2_processed" to indicate that the form has been sent to DHIS2 as an event

DHIS2 tracked entity attributes:

1. cchq_case_id: Used to refer to the corresponding CommCareHQ case. This is a hexadecimal UUID.

DHIS2 needs the following two projects:

1. "Pediatric Nutrition Assessment"
2. "Underlying Risk Assessment"


"""
from datetime import date
import uuid
from xml.etree import ElementTree
from apps.case.mock import CaseBlock
from apps.case.models import CommCareCase
from apps.case.xml import V2
from celery.schedules import crontab
from celery.task import periodic_task
from corehq.apps.es.cases import CaseES
from corehq.apps.es.forms import FormES
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from custom.dhis2.models import Dhis2Api, Dhis2OrgUnit, JsonApiRequest, JsonApiError
from django.conf import settings
from models import XFormInstance


# TODO: Do these belong in settings.py?
DOMAIN = 'barproject'
DEFAULT_COMMCARE_USER_ID = 'df2530dfc9f092e429b3d594a20e278x'  # Used when creating new cases  # TODO: Use a real user
DATA_ELEMENT_NAMES = {   # CCHQ form field names : DHIS2 project data element names
    # We could map to IDs, which would save an API request, but would reduce readability.
    'height': 'Height',
    'weight': 'Weight',
    'age': 'Age at time of visit',
    'bmi': 'Body-mass index',
}

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
                # TODO: Determine attributes.
            }
            result = dhis2_api.add_te_inst(dhis2_child, 'Child', ou_id=ou_id)
            # TODO: What does result look like?
            dhis2_child = result

        # Enroll in Pediatric Nutrition Assessment
        dhis2_api.enroll_in_id(dhis2_child, nutrition_id, today)

        # Enroll in Underlying Risk Assessment
        dhis2_api.enroll_in_id(dhis2_child, risk_id, today)

        # Set dhis2_te_inst_id in CCHQ to flag the case as pushed.
        commcare_user = CommCareUser.get(child['owner_id'])
        close = commcare_user.to_be_deleted() or not commcare_user.is_active
        caseblock = CaseBlock(
            create=False,
            case_id=child['_id'],
            version=V2,
            case_type=commcare_user.project.SOME_ATTRIBUTE.case_type,  # <-- TODO: What attribute?
            # commcare_user.project.call_center_config.case_type
            close=close,
            update={
                'dhis2_te_inst_id': dhis2_child['id'],
                # TODO: ...
            }
        )
        casexml = ElementTree.tostring(caseblock.as_xml())
        submit_case_blocks(casexml, commcare_user.project.name)


def pull_child_entities(domain, commcare_user_id, dhis2_children):
    """
    Create new child cases for nutrition tracking in CommCare.

    Sets dhis2_te_inst_id on new child cases, and cchq_case_id on DHIS2
    tracked entity instances. (cchq_case_id is initially unset because the
    case is new and does not exist in CommCare.)

    :param domain: The domain/project of the application
    :param commcare_user_id: The user to set as the owner of the child cases
    :param dhis2_children: A list of dictionaries of Child tracked entities
                           from the DHIS2 API where cchq_case_id is unset

    This fulfills the third requirement of `DHIS2 Integration`_.


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx
    """
    commcare_user = CommCareUser.get(commcare_user_id)
    close = commcare_user.to_be_deleted() or not commcare_user.is_active
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    for dhis2_child in dhis2_children:
        # Add each child separately. Although this is slower, it avoids problems if a DHIS2 API call fails
        case = get_case_by_dhis2_te_inst_id(dhis2_child['id'])
        if case:
            case_id = case['case_id']
        else:
            case_id = uuid.uuid4().hex
            caseblock = CaseBlock(
                create=True,
                case_id=case_id,
                owner_id=commcare_user_id,
                user_id=commcare_user_id,
                version=V2,
                case_type=commcare_user.project.SOME_ATTRIBUTE.case_type,  # <-- TODO: What attribute?
                update={
                    'dhis2_te_inst_id': dhis2_child['id'],
                    # TODO: ...
                }
            )
            casexml = ElementTree.tostring(caseblock.as_xml())
            submit_case_blocks(casexml, commcare_user.project.name)
        dhis2_child['cchq_case_id'] = case_id
        dhis2_api.update_te_inst(dhis2_child)


def get_children_only_theirs():
    """
    Returns a list of child entities that don't have cchq_case_id set
    """
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    return dhis2_api.gen_instances_with_unset('Child', 'cchq_case_id')


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
    pull_child_entities(DOMAIN, DEFAULT_COMMCARE_USER_ID, children)

    children = gen_children_only_ours(DOMAIN)
    push_child_entities(children)


def send_nutrition_data():
    """
    Send received nutrition data to DHIS2.

    This fulfills the fourth requirement of `DHIS2 Integration`_


    .. _DHIS2 Integration: https://www.dropbox.com/s/8djk1vh797t6cmt/WV Sri Lanka Detailed Requirements.docx

    """
    #
    # CommCareHQ will use the DHIS API to send received nutrition data to DHIS2
    # as an event that is associated with the correct entity, program, DHIS2
    # user and organization.
    #
    # 1. On a periodic basis, CommCareHQ will submit an appropriate event using
    #    the DHIS2 events API (Multiple Event with Registration) for any
    #    unprocessed Growth Monitoring forms.
    #
    dhis2_api = Dhis2Api(settings.DHIS2_HOST, settings.DHIS2_USERNAME, settings.DHIS2_PASSWORD)
    nutrition_id = dhis2_api.get_resource_id('program', 'Pediatric Nutrition Assessment')
    forms = []
    events = {'eventList': []}
    for form in get_unprocessed_growth_monitoring_forms():
        forms.append(form)
        event = dhis2_api.form_to_event(nutrition_id, form, DATA_ELEMENT_NAMES)
        events['eventList'].append(event)
    dhis2_api.send_events(events)
    mark_as_processed(forms)


def get_unprocessed_growth_monitoring_forms():
    #
    # 2. The event will only be submitted if the corresponding case has a DHIS2
    #    mapping (case properties that indicate the DHIS2 tracked entity
    #    instance and programs for the case). If the case is not yet mapped to
    #    DHIS2, the Growth Monitoring form will not be processed and could be
    #    processed in the future (if the case is later associated with a DHIS
    #    entity).
    #
    query = FormES().filter(
        # TODO: case must have dhis2_te_inst_id populated; this indicates that it's
        # been enrolled in both programs by push_child_entities()

        # TODO: and it must not have been processed before

    )
    result = query.run()
    if result.total:
        for doc in result.hits:
            yield XFormInstance.wrap(doc)


def mark_as_processed(forms):
    for form in forms:
        form.dhis2_processed = True
        form.save()
