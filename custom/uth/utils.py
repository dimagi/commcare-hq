from dimagi.utils.couch.database import get_db
from casexml.apps.case.models import CommCareCase
from lxml import etree


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
