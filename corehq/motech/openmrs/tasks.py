"""
Tasks are used to pull data from OpenMRS. They either use OpenMRS's
Reporting REST API to import cases on a regular basis (like weekly), or
its Atom Feed (daily or more) to track changes.
"""
from __future__ import absolute_import
import uuid
from collections import namedtuple
from datetime import datetime
from celery.schedules import crontab
from celery.task import task, periodic_task
from couchdbkit import ResourceNotFound
from jinja2 import Template
from requests import HTTPError
import time
from casexml.apps.case.mock import CaseBlock
from corehq import toggles
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.const import LookupErrors
from corehq.apps.case_importer.util import EXTERNAL_ID
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.locations.dbaccessors import get_all_users_by_location
from corehq.apps.locations.models import SQLLocation, LocationType
from corehq.apps.users.models import CommCareUser
from corehq.motech.openmrs.const import IMPORT_FREQUENCY_WEEKLY, IMPORT_FREQUENCY_MONTHLY
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.logger import logger
from corehq.motech.openmrs.models import POSIX_MILLISECONDS
from corehq.motech.openmrs.repeater_helpers import Requests
from corehq.motech.utils import b64_aes_decrypt
from toggle.shortcuts import find_domains_with_toggle_enabled


RowAndCase = namedtuple('RowAndCase', ['row', 'case'])
LOCATION_OPENMRS = 'openmrs_uuid'  # The location metadata key that maps to its corresponding OpenMRS location UUID


def parse_params(params, location=None):
    today = datetime.today().strftime('%Y-%m-%d')
    location_uuid = location.metadata[LOCATION_OPENMRS] if location else None

    parsed = {}
    for key, value in params.items():
        if isinstance(value, basestring) and '{{' in value:
            template = Template(value)
            value = template.render(today=today, location=location_uuid)
        parsed[key] = value
    return parsed


def get_openmrs_patients(requests, importer, location=None):
    endpoint = '/ws/rest/v1/reportingrest/reportdata/' + importer.report_uuid
    params = parse_params(importer.report_params, location)
    response = requests.get(endpoint, params=params)
    try:
        response.raise_for_status()
    except HTTPError:
        logger.debug(response.json())
        raise
    data = response.json()
    return data['dataSets'][0]['rows']  # e.g. ...
    #     [{u'familyName': u'Hornblower', u'givenName': u'Horatio', u'personId': 2},
    #      {u'familyName': u'Patient', u'givenName': u'John', u'personId': 3}]


def get_caseblock(patient, importer, owner_id):
    cast = {
        POSIX_MILLISECONDS: lambda x: datetime(*time.gmtime(x / 1000.0)[:6]).isoformat() + 'Z',
    }
    case_id = uuid.uuid4().hex
    name_columns = importer.name_columns.split(' ')
    case_name = ' '.join([patient[column] for column in name_columns])
    fields_to_update = {
        mapping.property: (cast[mapping.data_type](patient[mapping.column])
                           if mapping.data_type else
                           patient[mapping.column])
        for mapping in importer.column_map
    }
    return CaseBlock(
        create=True,
        case_id=case_id,
        owner_id=owner_id,
        user_id=owner_id,
        case_type=importer.case_type,
        case_name=case_name,
        external_id=patient[importer.external_id_column],
        update=fields_to_update,
    )


def get_commcare_users_by_location(domain_name, location_id):
    for user in get_all_users_by_location(domain_name, location_id):
        if user.is_commcare_user():
            yield user


def import_patients_to_location(requests, importer, domain_name, location):
    try:
        if location is None:
            owner = CommCareUser.get(importer.owner_id)
        else:
            # Don't assign cases to the location itself (until we have a project that needs to)
            owner = next(get_commcare_users_by_location(domain_name, location.location_id))
    except (ResourceNotFound, StopIteration):
        # Location has no users
        logger.error('Project space "{domain}" location "{location}" has no user to own imported cases'.format(
            domain=domain_name, location=location.name))
        return

    openmrs_patients = get_openmrs_patients(requests, importer, location)
    case_blocks = []
    for i, patient in enumerate(openmrs_patients):
        case, error = importer_util.lookup_case(
            EXTERNAL_ID,
            str(patient[importer.external_id_column]),
            domain_name,
            importer.case_type
        )
        if error == LookupErrors.NotFound:
            case_block = get_caseblock(patient, importer, owner.user_id)
            case_blocks.append(RowAndCase(i, case_block))

    submit_case_blocks(
        [cb.case.as_string() for cb in case_blocks],
        domain_name,
        username=owner.username,
        user_id=owner.user_id,
    )


@task(queue='background_queue')
def import_patients_to_domain(domain_name, force=False):
    """
    Iterates OpenmrsImporters of a domain, and imports patients

    :param domain_name: The name of the domain
    :param force: Import regardless of the configured import frequency / today's date
    """
    today = datetime.today()
    for importer in get_openmrs_importers_by_domain(domain_name):
        if not force and importer.import_frequency == IMPORT_FREQUENCY_WEEKLY and today.weekday() != 1:
            continue  # Import on Tuesdays
        if not force and importer.import_frequency == IMPORT_FREQUENCY_MONTHLY and today.day != 1:
            continue  # Import on the first of the month
        # TODO: ^^^ Make those configurable

        password = b64_aes_decrypt(importer.password)
        requests = Requests(importer.server_url, importer.username, password)
        if importer.location_type_name:
            try:
                location_type = LocationType.objects.get(domain=domain_name, name=importer.location_type_name)
            except LocationType.DoesNotExist:
                logger.error(
                    'No organization level named "{location_type}" found in project space "{domain}".'.format(
                        location_type=importer.location_type_name, domain=domain_name)
                )
                continue
            locations = SQLLocation.objects.filter(domain=domain_name, location_type=location_type).all()
            for location in locations:
                import_patients_to_location(requests, importer, domain_name, location)
        else:
            import_patients_to_location(requests, importer, domain_name, None)


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
def track_changes():
    """
    Uses the OpenMRS Atom Feed to track changes
    """
    pass
