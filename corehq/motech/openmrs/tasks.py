"""
Tasks are used to pull data from OpenMRS. They either use OpenMRS's
Reporting REST API to import cases on a regular basis (like weekly), or
its Atom Feed (daily or more) to track changes.
"""
import uuid
from collections import namedtuple
from datetime import datetime
from functools import partial

from celery.schedules import crontab
from celery.task import periodic_task, task
from jinja2 import Template

from casexml.apps.case.mock import CaseBlock
from corehq.apps.groups.models import Group
from corehq.apps.users.cases import get_wrapped_owner
from toggle.shortcuts import find_domains_with_toggle_enabled

from corehq import toggles
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.const import LookupErrors
from corehq.apps.case_importer.util import EXTERNAL_ID
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.dbaccessors import get_one_commcare_user_at_location
from corehq.apps.locations.models import LocationType, SQLLocation
from corehq.motech.openmrs.atom_feed import (
    get_feed_updates,
    import_encounter,
    update_patient,
)
from corehq.motech.openmrs.const import (
    ATOM_FEED_NAME_ENCOUNTER,
    ATOM_FEED_NAME_PATIENT,
    OPENMRS_ATOM_FEED_POLL_INTERVAL,
    OPENMRS_IMPORTER_DEVICE_ID_PREFIX,
    XMLNS_OPENMRS,
)
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.models import POSIX_MILLISECONDS, OpenmrsImporter
from corehq.motech.openmrs.repeaters import OpenmrsRepeater
from corehq.motech.openmrs.serializers import openmrs_timestamp_to_isoformat
from corehq.motech.requests import Requests
from corehq.motech.utils import b64_aes_decrypt

RowAndCase = namedtuple('RowAndCase', ['row', 'case'])
# REQUEST_TIMEOUT is 5 minutes, but reports can take up to an hour
REPORT_REQUEST_TIMEOUT = 60 * 60
# The location metadata key that maps to its corresponding OpenMRS location UUID
LOCATION_OPENMRS = 'openmrs_uuid'


def parse_params(params, location=None):
    """
    Inserts date and OpenMRS location UUID into report params
    """
    today = datetime.today().strftime('%Y-%m-%d')
    location_uuid = location.metadata[LOCATION_OPENMRS] if location else None

    parsed = {}
    for key, value in params.items():
        if isinstance(value, str) and '{{' in value:
            template = Template(value)
            value = template.render(today=today, location=location_uuid)
        parsed[key] = value
    return parsed


def get_openmrs_patients(requests, importer, location=None):
    """
    Send request to OpenMRS Reporting API and return results
    """
    endpoint = f'/ws/rest/v1/reportingrest/reportdata/{importer.report_uuid}'
    params = parse_params(importer.report_params, location)
    response = requests.get(endpoint, params=params, raise_for_status=True,
                            timeout=REPORT_REQUEST_TIMEOUT)
    data = response.json()
    return data['dataSets'][0]['rows']  # e.g. ...
    #     [{u'familyName': u'Hornblower', u'givenName': u'Horatio', u'personId': 2},
    #      {u'familyName': u'Patient', u'givenName': u'John', u'personId': 3}]


def get_case_properties(patient, importer):
    as_isoformat = partial(openmrs_timestamp_to_isoformat,
                           tz=importer.get_timezone())
    cast = {
        POSIX_MILLISECONDS: as_isoformat,
    }
    name_columns = importer.name_columns.split(' ')
    case_name = ' '.join([patient[column] for column in name_columns])
    fields_to_update = {
        mapping.property: (cast[mapping.data_type](patient[mapping.column])
                           if mapping.data_type else
                           patient[mapping.column])
        for mapping in importer.column_map
    }
    return case_name, fields_to_update


def get_addpatient_caseblock(patient, importer, owner_id):
    """
    Creates a new case with imported patient details.
    """
    case_id = uuid.uuid4().hex
    case_name, fields_to_update = get_case_properties(patient, importer)
    return CaseBlock(
        create=True,
        case_id=case_id,
        owner_id=owner_id,
        case_type=importer.case_type,
        case_name=case_name,
        external_id=patient[importer.external_id_column],
        update=fields_to_update,
    )


def get_updatepatient_caseblock(case, patient, importer):
    """
    Updates a case with imported patient details. Does not change owner.
    """
    case_name, fields_to_update = get_case_properties(patient, importer)
    return CaseBlock(
        create=False,
        case_id=case.get_id,
        case_name=case_name,
        update=fields_to_update,
    )


def import_patients_of_owner(requests, importer, domain_name, owner_id, location=None):
    openmrs_patients = get_openmrs_patients(requests, importer, location)
    case_blocks = []
    for i, patient in enumerate(openmrs_patients):
        case, error = importer_util.lookup_case(
            EXTERNAL_ID,
            str(patient[importer.external_id_column]),
            domain_name,
            importer.case_type
        )
        if error is None:
            case_block = get_updatepatient_caseblock(case, patient, importer)
            case_blocks.append(RowAndCase(i, case_block))
        elif error == LookupErrors.NotFound:
            case_block = get_addpatient_caseblock(patient, importer, owner_id)
            case_blocks.append(RowAndCase(i, case_block))

    submit_case_blocks(
        [cb.case.as_text() for cb in case_blocks],
        domain_name,
        device_id=f'{OPENMRS_IMPORTER_DEVICE_ID_PREFIX}{importer.get_id}',
        xmlns=XMLNS_OPENMRS,
    )


def import_patients_to_domain(domain_name, force=False):
    """
    Iterates OpenmrsImporters of a domain, and imports patients

    Who owns the imported cases?

    If `importer.owner_id` is set, then the server will be queried
    once. All patients, regardless of their location, will be assigned
    to the mobile worker whose ID is `importer.owner_id`.

    If `importer.location_type_name` is set, then check whether the
    OpenmrsImporter's location is set with `importer.location_id`.

    If `importer.location_id` is given, then the server will be queried
    for each location among its descendants whose type is
    `importer.location_type_name`. The request's query parameters will
    include that descendant location's OpenMRS UUID. Imported cases
    will be owned by the first mobile worker in that location.

    If `importer.location_id` is given, then the server will be queried
    for each location in the project space whose type is
    `importer.location_type_name`. As when `importer.location_id` is
    specified, the request's query parameters will include that
    location's OpenMRS UUID, and imported cases will be owned by the
    first mobile worker in that location.

    ..NOTE:: As you can see from the description above, if
             `importer.owner_id` is set then `importer.location_id` is
             not used.

    :param domain_name: The name of the domain
    :param force: Import regardless of the configured import frequency / today's date
    """
    for importer in get_openmrs_importers_by_domain(domain_name):
        if importer.should_import_today() or force:
            import_patients_with_importer.delay(importer.to_json())


@task(serializer='pickle', queue='background_queue')
def import_patients_with_importer(importer_json):
    importer = OpenmrsImporter.wrap(importer_json)
    password = b64_aes_decrypt(importer.password)
    requests = Requests(importer.domain, importer.server_url, importer.username, password)
    if importer.location_type_name:
        try:
            location_type = LocationType.objects.get(domain=importer.domain, name=importer.location_type_name)
        except LocationType.DoesNotExist:
            logger.error(
                f'No organization level named "{importer.location_type_name}" '
                f'found in project space "{importer.domain}".'
            )
            return
        if importer.location_id:
            location = SQLLocation.objects.filter(domain=importer.domain).get(importer.location_id)
            locations = location.get_descendants.filter(location_type=location_type)
        else:
            locations = SQLLocation.objects.filter(domain=importer.domain, location_type=location_type)
        for location in locations:
            # Assign cases to the first user in the location, not to the location itself
            owner = get_one_commcare_user_at_location(importer.domain, location.location_id)
            if not owner:
                logger.error(
                    f'Project space "{importer.domain}" at location '
                    f'"{location.name}" has no user to own cases imported '
                    f'from OpenMRS Importer "{importer}"'
                )
                continue
            # The same report is fetched for each location. WE DO THIS
            # ASSUMING THAT THE LOCATION IS USED IN THE REPORT
            # PARAMETERS. If not, OpenMRS will return THE SAME PATIENTS
            # multiple times and they will be assigned to a different
            # user each time.
            import_patients_of_owner(requests, importer, importer.domain, owner.user_id, location)
    elif importer.owner_id:
        if not is_valid_owner(importer.owner_id):
            logger.error(
                f'Error importing patients for project space "{importer.domain}" '
                f'from OpenMRS Importer "{importer}": owner_id "{importer.owner_id}" '
                'is invalid.'
            )
            return
        import_patients_of_owner(requests, importer, importer.domain, importer.owner_id)
    else:
        logger.error(
            f'Error importing patients for project space "{importer.domain}" from '
            f'OpenMRS Importer "{importer}": Unable to determine the owner of '
            'imported cases without either owner_id or location_type_name'
        )


def is_valid_owner(owner_id):
    owner = get_wrapped_owner(owner_id)
    if not owner:
        return False
    if isinstance(owner, Group) and not owner.case_sharing:
        return False
    return True


@periodic_task(
    run_every=crontab(minute=4, hour=4),
    queue='background_queue'
)
def import_patients():
    """
    Uses the Reporting REST API to import patients
    """
    for domain_name in find_domains_with_toggle_enabled(toggles.OPENMRS_INTEGRATION):
        import_patients_to_domain(domain_name)


@task(queue='background_queue')
def poll_openmrs_atom_feeds(domain_name):
    for repeater in OpenmrsRepeater.by_domain(domain_name):
        if repeater.atom_feed_enabled and not repeater.paused:
            patient_uuids = get_feed_updates(repeater, ATOM_FEED_NAME_PATIENT)
            encounter_uuids = get_feed_updates(repeater, ATOM_FEED_NAME_ENCOUNTER)
            for patient_uuid in patient_uuids:
                update_patient(repeater, patient_uuid)
            for encounter_uuid in encounter_uuids:
                import_encounter(repeater, encounter_uuid)


@periodic_task(
    run_every=crontab(**OPENMRS_ATOM_FEED_POLL_INTERVAL),
    queue='background_queue'
)
def track_changes():
    """
    Uses the OpenMRS Atom Feed to track changes
    """
    domains = find_domains_with_toggle_enabled(toggles.OPENMRS_INTEGRATION)
    for domain in domains:
        poll_openmrs_atom_feeds.delay(domain)
