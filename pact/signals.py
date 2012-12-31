import pdb
from celery.task.base import subtask
from corehq.apps.users.models import CommCareUser
from couchforms.signals import xform_saved
import logging
import simplejson
#from pactpatient import caseapi
from pact.enums import PACT_DOTS_DATA_PROPERTY
from pact.utils import get_case_id
from receiver.signals import successful_form_received
from pact.tasks import recalculate_dots_data, eval_dots_block
import traceback
from django.conf import settings

BLOCKING = True

def process_dots_submission(sender, xform, **kwargs):
    try:
#        pdb.set_trace()
        if xform.xmlns != "http://dev.commcarehq.org/pact/dots_form":
            return

            #grrr, if we were on celery 3.0, we could do this!
        #        chain = eval_dots_block.s(xform.to_json()) | recalculate_dots_data.s(case_id)
        #        chain()

        #2.4.5 subtasking:
#        blocking =  kwargs.get("blocking", False)
        if BLOCKING:
            eval_dots_block(xform.to_json())
            case_id = get_case_id(xform)
            recalculate_dots_data(case_id)
        else:
            eval_dots_block.delay(xform.to_json(), callback=subtask(recalculate_dots_data))

    except Exception, ex:
        logging.error("Error processing the submission due to an unknown error: %s" % ex)
        tb = traceback.format_exc()
        print tb

#xform_saved.connect(process_dots_submission)
successful_form_received.connect(process_dots_submission)

