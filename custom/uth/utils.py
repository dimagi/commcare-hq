from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from lxml import etree
import os
from datetime import datetime, timedelta
import uuid
from casexml.apps.case import process_cases
import io
from django.core.files.uploadedfile import UploadedFile


def all_scan_cases(domain, scanner_serial, scan_id):
    return get_db().view(
        'uth/uth_lookup',
        startkey=[domain, scanner_serial, scan_id],
        endkey=[domain, scanner_serial, scan_id, {}],
    ).all()


def match_case(domain, scanner_serial, scan_id, date=None):
    results = all_scan_cases(domain, scanner_serial, scan_id)

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


def render_xform(files, exam_uuid, patient_case_id=None):
    xform_template = None
    template_path = os.path.join(
        os.path.dirname(__file__),
        'upload_form.xml.template'
    )
    with open(template_path, 'r') as fin:
        xform_template = fin.read()

    def case_attach_block(key, filename):
        return '<n0:%s src="%s" from="local"/>' % (key, os.path.split(filename)[-1])
    case_attachments = [case_attach_block(f['identifier'], f['filename']) for f in files]

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
        'exam_id': 'TODO',
        'case_name': 'TODO',
    }

    final_xml = xform_template % format_dict
    return final_xml


def create_case(case_id, zip_file, patient_case_id=None):
    files = []
    for name in zip_file.namelist():
        if name[-4:].lower() == '.xml':
            # we don't need to attach these to the case
            continue

        filename = os.path.basename(name)

        # TODO fix this up so it doesn't rely on the PT_PPS.XML file
        # having already been filtered
        scan = os.path.basename(os.path.dirname(name))

        files.append({
            'identifier': scan,
            'filename': filename,
            'data': io.BytesIO(zip_file.read(name))
        })

    xform = render_xform(files, case_id, patient_case_id)

    file_dict = {}

    for f in files:
        file_dict[f['filename']] = UploadedFile(f['data'], f['filename'])

    # TODO post_xform_to_couch is a test only function
    from couchforms.util import post_xform_to_couch

    form = post_xform_to_couch(xform, file_dict)
    form.domain = 'vscan_domain'
    return process_cases(form)


def get_patient_config_from_zip(zip_file):
    return zip_file.read(
        [f for f in zip_file.namelist() if 'PT_PPS.XML' in f][0]
    )
