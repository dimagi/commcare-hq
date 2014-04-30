from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from lxml import etree
import os
from datetime import datetime, timedelta
import uuid
from casexml.apps.case import process_cases


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


def render_xform(zip_file, exam_uuid, patient_case_id=None):
    xform_template = None
    template_path = os.path.join(
        os.path.dirname(__file__),
        'upload_form.xml.template'
    )
    with open(template_path, 'r') as fin:
        xform_template = fin.read()

    # TODO boooo don't load from file like this
    content_dir = os.path.join(os.path.dirname(__file__), 'tests', 'data', 'unzipped', 'create_case')
    file_tuples = []
    for subdir in get_subdirectories(content_dir):
        tup = os.listdir(os.path.join(content_dir, subdir))
        file_tuples.append((
            tup[1].split('.')[0],
            tup[1],
            os.path.join(content_dir, subdir, tup[1])
        ))


    def case_attach_block(key, filename):
        return '<n0:%s src="%s" from="local"/>' % (key, os.path.split(filename)[-1])
    case_attachments = [case_attach_block(t[0], t[1]) for t in file_tuples]

    def form_attachment_group(key, filename):
        return '<n0:%s src="%s" from="local"/>' % (key, os.path.split(filename)[-1])
    attach_group = [form_attachment_group(t[0], t[1]) for t in file_tuples]


    submit_id = uuid.uuid4().hex

    #we're making a new caseid to subcase this to the patient
    submit_case_id = uuid.uuid4().hex

    format_dict = {
        "time_start": (datetime.utcnow() - timedelta(seconds=5)).strftime('%Y-%m-%dT%H:%M:%SZ'),
        "time_end": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        "modified_date": datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
        "user_id": 'TODO',
        "username": 'TODO',
        "doc_id": submit_id,
        "case_id": submit_case_id,
        "patient_case_id": patient_case_id,
        "case_attachments": ''.join(case_attachments),
        "attachment_groups": ''.join(attach_group), # TODO this got removed from the form
        "exam_id": 'TODO',
        "upload_case_id": 'TODO',
        "readable_upload_id": 'TODO',
    }

    final_xml = xform_template % format_dict
    return final_xml, file_tuples


def create_case(case_id, zip_file):
    xform, file_tuples = render_xform(zip_file, case_id)
    print xform
    from corehq.apps.receiverwrapper import submit_form_locally
    file_dict = {}
    for tup in file_tuples:
        f = open(tup[2], 'r')
        from django.core.files.uploadedfile import UploadedFile
        file_dict[tup[1]] = UploadedFile(f, tup[0])

    # {'./submodules/casexml-src/casexml/apps/case/tests/data/attachments/fruity.jpg': <UploadedFile: fruity_file (None)>}
    from couchforms.util import post_xform_to_couch
    form = post_xform_to_couch(xform, file_dict)
    form.domain = 'vscan_domain'
    print "***"
    print file_dict
    print form.attachments
    print "***"
    import bpdb; bpdb.set_trace()
    process_cases(form)
