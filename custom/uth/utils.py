from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from lxml import etree
import os
from datetime import datetime, timedelta
import uuid
from casexml.apps.case import process_cases
from couchforms.util import create_and_lock_xform
from django.core.files.uploadedfile import UploadedFile
from custom.uth.const import UTH_DOMAIN
import re


def all_scan_cases(scanner_serial, scan_id):
    # this is shown on device and stored on the case with no leading zeroes
    # but has them on the file itself
    scan_id = scan_id.lstrip('0')

    return get_db().view(
        'uth/uth_lookup',
        startkey=[UTH_DOMAIN, scanner_serial, scan_id],
        endkey=[UTH_DOMAIN, scanner_serial, scan_id, {}],
    ).all()


def match_case(scanner_serial, scan_id, date=None):
    results = all_scan_cases(scanner_serial, scan_id)

    if results:
        return CommCareCase.get(results[-1]['value'])
    else:
        return None


def get_case_id(patient_xml):
    """
    This is the case_id if it's extracted, assumed to be in the PatientID
    However, there's a nonzero chance of them either forgetting to scan it
    Or putting it in the wrong field like PatientsName
    """
    exam_root = etree.fromstring(patient_xml)
    case_id = exam_root.find("PatientID").text
    if case_id == '(_No_ID_)':
        return None
    else:
        return case_id


def get_study_id(patient_xml):
    """
    The GUID the sonosite generates for the particular exam
    """
    exam_root = etree.fromstring(patient_xml)
    return exam_root.find("SonoStudyInstanceUID").text


def get_subdirectories(directory):
    # TODO make sure this is needed
    return [d for d in os.listdir(directory) if os.path.isdir(os.path.join(directory, d))]


def load_template(filename):
    xform_template = None
    template_path = os.path.join(
        os.path.dirname(__file__),
        filename
    )
    with open(template_path, 'r') as fin:
        xform_template = fin.read()

    return xform_template


def case_attach_block(key, filename):
    return '<n0:%s src="%s" from="local"/>' % (key, os.path.split(filename)[-1])


def render_sonosite_xform(files, exam_uuid, patient_case_id=None):
    """
    Render the xml needed to create a new case for a given
    screening. This case will be a subcase to the `exam_uuid` case,
    which belongs to the patient.
    """
    xform_template = load_template('upload_form.xml.template')
    case_attachments = [case_attach_block(identifier(f), f) for f in files]

    format_dict = {
        'time_start': (datetime.utcnow() - timedelta(seconds=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'time_end': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'modified_date': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'user_id': 'f72265c0-362a-11e0-9e24-005056aa7fb5',  #TODO
        'username': 'fakeuser@dimagi.com',  #TODO
        'doc_id': uuid.uuid4().hex,
        'case_id': uuid.uuid4().hex,
        'patient_case_id': patient_case_id,
        'case_attachments': ''.join(case_attachments),
        'exam_id': exam_uuid,
        'case_name': 'TODO',
    }

    final_xml = xform_template % format_dict
    return final_xml


def render_vscan_xform(case_id, files):
    """
    Render the xml needed add attachments to the patients case.
    """
    xform_template = load_template('vscan_form.xml.template')
    case_attachments = [
        case_attach_block(os.path.split(f)[-1], f) for f in files
    ]

    format_dict = {
        'time_start': (datetime.utcnow() - timedelta(seconds=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'time_end': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'modified_date': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        'user_id': 'f72265c0-362a-11e0-9e24-005056aa7fb5',  #TODO
        'username': 'fakeuser@dimagi.com',  #TODO
        'doc_id': uuid.uuid4().hex,
        'case_id': case_id,
        'case_attachments': ''.join(case_attachments),
    }

    final_xml = xform_template % format_dict
    return final_xml


def identifier(filename):
    """
    File names are of the format: 09.44.32 hrs __[0000312].jpeg and we need
    to filter out the 0000312 part to use as identifier
    """
    match = re.search('\[(\d+)\]', filename)
    if match:
        return 'attachment' + match.group(1)
    else:
        # if we can't match, lets hope returning the filename works
        return filename


def create_case(case_id, files, patient_case_id=None):
    """
    Handle case submission for the sonosite endpoint
    """
    # we already parsed what we need from this, so can just remove it
    # without worrying we will need it later
    files.pop('PT_PPS.XML', '')

    xform = render_sonosite_xform(files, case_id, patient_case_id)

    file_dict = {}
    for f in files:
        file_dict[f] = UploadedFile(files[f], f)

    lock = create_and_lock_xform(
        xform,
        attachments=file_dict,
        process=None,
        domain=UTH_DOMAIN,
    )
    lock.obj.domain = UTH_DOMAIN

    return process_cases(lock.obj)


def attach_images_to_case(case_id, files):
    """
    Handle case submission for the vscan endpoint
    """
    xform = render_vscan_xform(case_id, files)

    file_dict = {}
    for f in files:
        identifier = os.path.split(f)[-1]
        file_dict[identifier] = UploadedFile(files[f], identifier)

    lock = create_and_lock_xform(
        xform,
        attachments=file_dict,
        process=None,
        domain=UTH_DOMAIN,
    )
    lock.obj.domain = UTH_DOMAIN

    return process_cases(lock.obj)
