import logging
from xml.etree import ElementTree
from django.conf import settings
from datetime import datetime, timedelta
from pytz import timezone
import simplejson
from casexml.apps.case.signals import process_cases
from casexml.apps.case.tests import CaseBlock
from casexml.apps.case.xml import V2
from couchforms.util import post_xform_to_couch
from dimagi.utils import make_time
from dimagi.utils.printing import print_pretty_xml
from pact.enums import DAY_SLOTS_BY_TIME


def isodate_string(date):
    if date: return isodate.datetime_isoformat(date) + "Z"
    return ""

def get_regimen_code_arr(str_regimen):
    """
    Helper function to decode regimens for both the old style regimens (in REGIMEN_CHOICES) as well as the new style
    regimens as required in the technical specs above.

    should return an array of day slot indices.
    """
    if str_regimen is None or str_regimen == '' or str_regimen == 'None':
        return []


    #legacy handling
    if str_regimen.lower() == 'qd':
        return [0]
    elif str_regimen.lower() == 'qd-am':
        return [0]
    elif str_regimen.lower() == 'qd-pm':
        return [2]
    elif str_regimen.lower() == 'bid':
        return [0, 2]
    elif str_regimen.lower() == 'qid':
        return [0, 1, 2, 3]
    elif str_regimen.lower() == 'tid':
        return [0, 1, 2]
    elif str_regimen.lower() == '':
        return []

    #newer handling, a split string
    splits = str_regimen.split(',')
    ret = []
    for x in splits:
        if x in DAY_SLOTS_BY_TIME.keys():
            ret.append(DAY_SLOTS_BY_TIME[x])
        else:
            logging.error("value error, the regimen string is incorrect for the given patient, returning blank")
            ret = []
    return ret

def get_dots_data(self):
    """
    Return JSON-ready array of the DOTS block for given patient.
    Pulling properties from PATIENT document.  patient document trumps casedoc in this use case.
    """
    startdate = datetime.utcnow()
    ret = {}
    try:
        art_arr = get_regimen_code_arr(self.art_regimen.lower())
        art_num = len(art_arr)
    except:
        art_num = 0
        art_arr = []
        logging.error("Patient does not have a set art regimen")

    try:
        non_art_arr = get_regimen_code_arr(self.non_art_regimen.lower())
        non_art_num = len(non_art_arr)
    except:
        non_art_num = 0
        non_art_arr = []
        logging.error("Patient does not have a set non art regimen")


    ret['regimens'] = [
        non_art_num, #non art is 0
        art_num,    #art is 1
    ]
    ret['regimen_labels'] = [
        non_art_arr,
        art_arr
    ]

    ret['days'] = []
    #dmyung - hack to have it be timezone be relative specific to the eastern seaboard
    #ret['anchor'] = isodate.strftime(datetime.now(tz=timezone(settings.TIME_ZONE)), "%d %b %Y")
    ret['anchor'] = datetime.now(tz=timezone(settings.TIME_ZONE)).strftime("%d %b %Y")


    for delta in range(21):
        date = startdate - timedelta(days=delta)
        day_arr = self.dots_casedata_for_day(date)
        ret['days'].append(day_arr)
    ret['days'].reverse()
    return ret

def calculate_regimen_caseblock(case):
    """
    Forces all labels to be reset back to the labels set on the patient document.

    patient document trumps casedoc in this case.
    """
    update_ret = {}
    for prop_fmt in ['dot_a_%s', 'dot_n_%s']:
        if prop_fmt[4] == 'a':
            code_arr = get_regimen_code_arr(case.art_regimen)
            update_ret['artregimen'] = str(len(code_arr)) if len(code_arr) > 0 else ""
        elif prop_fmt[4] == 'n':
            code_arr = get_regimen_code_arr(case.non_art_regimen)
            update_ret['nonartregimen'] = str(len(code_arr)) if len(code_arr) > 0 else ""
        digit_strings = ["zero", 'one', 'two', 'three','four']
        for x in range(1,5):
            prop_prop = prop_fmt % digit_strings[x]
            if x > len(code_arr):
                update_ret[prop_prop] = ''
            else:
                update_ret[prop_prop] = str(code_arr[x-1])
    return update_ret

def submit_blocks(case_blocks, sender_name):
    form = ElementTree.Element("data")
    form.attrib['xmlns'] = "http://dev.commcarehq.org/pact/patientupdate"
    form.attrib['xmlns:jrm'] = "http://openrosa.org/jr/xforms"
    for block in case_blocks:
        form.append(block)
    submission_xml_string = ElementTree.tostring(form)
    print "#################################\nCase Update Submission: %s" % sender_name
    print_pretty_xml(submission_xml_string)
    print "#################################\n\n"
    xform_posted = post_xform_to_couch(ElementTree.tostring(form))
    process_cases(sender=sender_name, xform=xform_posted)
    return xform_posted

def recompute_dots_casedata(case):
    """
    Recompute and reset the ART regimen and NONART regimen to whatever the server says it is, in the case where there's an idiosyncracy with how the phone has it set.
    """
    #reconcile and resubmit DOT json - commcare2.0
    if case.opened_on is None:
        #hack calculate the opened on date from the first xform
        opened_date = case.actions[0].date
    else:
        opened_date = case.opened_on

    owner_id = case.owner_id
    update_dict = calculate_regimen_caseblock(case)
    update_dict['pactid'] =  case.pactid

    dots_data = get_dots_data(case)
    update_dict['dots'] =  simplejson.dumps(dots_data)

    caseblock = CaseBlock(case._id, update=update_dict, owner_id=owner_id, external_id=case.pactid, case_type=case.type, date_opened=opened_date, close=False, date_modified=make_time().strftime("%Y-%m-%dT%H:%M:%SZ"), version=V2)
    #'2011-08-24T07:42:49.473-07') #make_time())

    case_blocks = [caseblock.as_xml(format_datetime=isodate_string)]
    return submit_blocks(case_blocks, "compute_pactpatient_dots")