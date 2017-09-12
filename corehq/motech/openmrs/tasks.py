"""
Tasks are used to pull data from OpenMRS. They either use OpenMRS's 
Reporting REST API to import cases on a regular basis (like weekly), or 
its Atom Feed (daily or more) to track changes.
"""
import uuid
from base64 import b64decode
from collections import namedtuple
from datetime import datetime
import bz2
from celery.schedules import crontab
from celery.task import task, periodic_task
from casexml.apps.case.mock import CaseBlock
from corehq import toggles
from corehq.apps.case_importer import util as importer_util
from corehq.apps.case_importer.const import LookupErrors
from corehq.apps.case_importer.util import EXTERNAL_ID
from corehq.apps.hqcase.utils import submit_case_blocks
from corehq.apps.users.models import CommCareUser
from corehq.motech.openmrs.const import IMPORT_FREQUENCY_WEEKLY, IMPORT_FREQUENCY_MONTHLY
from corehq.motech.openmrs.dbaccessors import get_openmrs_importers_by_domain
from corehq.motech.openmrs.repeater_helpers import Requests
from toggle.shortcuts import find_domains_with_toggle_enabled


RowAndCase = namedtuple('RowAndCase', ['row', 'case'])
# TODO: Move to config once column names are mapped:
OPENMRS_ID = 'Old Identification Number'  # or 'OpenMRS Identification Number' depending on project


def get_openmrs_patients(requests, report_uuid):
    endpoint = '/ws/rest/v1/reportingrest/reportdata/' + report_uuid
    resp = requests.get(endpoint)
    data = resp.json()
    return data['dataSets'][0]['rows']  # e.g. ...
    #     [{u'familyName': u'Hornblower', u'givenName': u'Horatio', u'personId': 2},
    #      {u'familyName': u'Patient', u'givenName': u'John', u'personId': 3}]


def get_caseblock(patient, case_type, owner_id):
    case_id = uuid.uuid4().hex
    case_name = ' '.join((patient['givenName'], patient['familyName']))
    fields_to_update = {
        # TODO: Map column names to properties similar to openmrs_config.case_config
        'nid': patient['NID'],
        'nome': patient['nome_inicial'],
        'apelido': patient['apelido'],
        'numero_de_telefone': patient['Telefone'],
        'provincia': patient['provincia'],
        'distrito': patient['distrito'],
        'avenida': patient['localidade'],
        'bairro': patient['bairro'],
        'celula': patient['Referencia'],
        'genero': patient['genero'],
        'data_do_nacimento': patient['data_do_nacimento'],  # "sql-date"
        'numero_de_filhos': patient['filhos'],
        'numero_de_filhos_testados': patient['testados'],
        'numero_de_filhos_positivos': patient['positivos'],
        'parceiro_serologia': patient['serologia'],
        'numero_conviventes': patient['conviventes'],
        'tarv_elegivel': patient['tarv_elegivel'],
        'estado_tarv': patient['estado_tarv'],
        'gravida': patient['gravida'],
        'coinfectado': patient['coinfectado'],
        'a_faltar': patient['a_faltar'],
        'data_ultima_consulta': patient['data_ultima_consulta'],  # "sql-timestamp"
        'data_proxima_consulta': patient['data_proxima_consulta'],  # "sql-timestamp"
    }
    return CaseBlock(
        create=True,
        case_id=case_id,
        owner_id=owner_id,
        user_id=owner_id,
        case_type=case_type,
        case_name=case_name,
        external_id=patient[OPENMRS_ID],
        update=fields_to_update,
    )


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

        password = bz2.decompress(b64decode(importer.password))
        requests = Requests(importer.url, importer.username, password)
        openmrs_patients = get_openmrs_patients(requests, importer.report_uuid)
        case_blocks = []
        for i, patient in enumerate(openmrs_patients):
            case, error = importer_util.lookup_case(
                EXTERNAL_ID,
                str(patient[OPENMRS_ID]),
                domain_name,
                importer.case_type
            )
            if error == LookupErrors.NotFound:
                case_block = get_caseblock(patient, importer.case_type, importer.owner_id)
                case_blocks.append(RowAndCase(i, case_block))

        owner = CommCareUser.get(importer.owner_id)
        form, cases = submit_case_blocks(
            [cb.case.as_string() for cb in case_blocks],
            domain_name,
            username=owner.username,
            user_id=importer.owner_id,
        )


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
