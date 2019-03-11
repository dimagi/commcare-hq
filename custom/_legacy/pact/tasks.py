from __future__ import absolute_import
from __future__ import unicode_literals
import traceback
from datetime import datetime
from xml.etree import cElementTree as ElementTree

from celery.task import task
import json
from casexml.apps.case.mock import CaseBlock
from corehq.apps.hqcase.utils import submit_case_blocks

from couchforms.models import XFormInstance
from dimagi.utils.logging import notify_exception
from pact.enums import PACT_DOTS_DATA_PROPERTY
from pact.utils import get_case_id
import six


DOT_RECOMPUTE = True


@task(serializer='pickle', ignore_result=True)
def recalculate_dots_data(case_id, cc_user, sync_token=None):
    """
    Recalculate the dots data and resubmit calling the pact api for dot recompute
    """
    from pact.models import PactPatientCase
    from pact.api import recompute_dots_casedata
    if DOT_RECOMPUTE:
        try:
            casedoc = PactPatientCase.get(case_id)
            recompute_dots_casedata(casedoc, cc_user, sync_token=sync_token)
        except Exception as ex:
            tb = traceback.format_exc()
            notify_exception(None, message="PACT error recomputing DOTS case block: %s\n%s" % (ex, tb))


@task(serializer='pickle', ignore_result=True)
def eval_dots_block(xform_json, callback=None):
    """
    Evaluate the dots block in the xform submission and put it in the computed_ block for the xform.
    """
    case_id = get_case_id(xform_json)
    do_continue = False

    #first, set the pact_data to json if the dots update stuff is there.
    try:
        if 'processed' in xform_json.get(PACT_DOTS_DATA_PROPERTY, {}):
            #already processed, skipping
            return

        xform_json[PACT_DOTS_DATA_PROPERTY] = {}
        if not isinstance(xform_json['form']['case'].get('update', None), dict):
            #no case update property, skipping
            pass
        else:
            #update is a dict
            if 'dots' in xform_json['form']['case']['update']:
                dots_json = xform_json['form']['case']['update']['dots']
                if isinstance(dots_json, str) or isinstance(dots_json, six.text_type):
                    json_data = json.loads(dots_json)
                    xform_json[PACT_DOTS_DATA_PROPERTY]['dots'] = json_data
                do_continue=True
            else:
                #no dots data in doc
                pass
        xform_json[PACT_DOTS_DATA_PROPERTY]['processed']=datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        XFormInstance.get_db().save_doc(xform_json)

    except Exception as ex:
        #if this gets triggered, that's ok because web entry don't got them
        tb = traceback.format_exc()
        notify_exception(None, message="PACT error evaluating DOTS block docid %s, %s\n\tTraceback: %s" % (xform_json['_id'], ex, tb))


def set_schedule_case_properties(pact_case):
    """
    Sets the required schedule case properties on the case if they are different from the current
    case properties. See the README for more information.
    """
    SCHEDULE_CASE_PROPERTY_PREFIX = 'dotSchedule'
    DAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
    current_schedule = pact_case.current_schedule
    if current_schedule is not None:
        to_change = {}
        for day in DAYS:
            case_property_name = '{}{}'.format(SCHEDULE_CASE_PROPERTY_PREFIX, day)
            from_case = getattr(pact_case, case_property_name, None)
            from_schedule = current_schedule[day]
            if (from_case or from_schedule) and from_case != from_schedule:
                to_change[case_property_name] = current_schedule[day]
        if to_change:
            case_block = CaseBlock(
                case_id=pact_case._id,
                update=to_change,
            ).as_xml()
            submit_case_blocks(
                [ElementTree.tostring(case_block)],
                'pact',
                device_id=__name__ + ".set_schedule_case_properties",
            )
