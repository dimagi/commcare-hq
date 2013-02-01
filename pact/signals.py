from corehq.apps.users.models import  CouchUser
from dimagi.utils.logging import notify_exception
from pact.utils import get_case_id
from receiver.signals import successful_form_received
import traceback

#placeholder for doing blocking vs. async via celery
BLOCKING = True

def process_dots_submission(sender, xform, **kwargs):
    from celery.task.base import subtask
    from pact.tasks import recalculate_dots_data, eval_dots_block
    try:
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
            #get user from xform
            user_id = xform.metadata.userID
            cc_user = CouchUser.get_by_user_id(user_id)
            recalculate_dots_data(case_id, cc_user)
        else:
            eval_dots_block.delay(xform.to_json(), callback=subtask(recalculate_dots_data))

    except Exception, ex:
        tb = traceback.format_exc()
        notify_exception(None, message="Error processing PACT DOT submission due to an unknown error: %s\n\tTraceback: %s" % (ex, tb))

#xform_saved.connect(process_dots_submission)
successful_form_received.connect(process_dots_submission)

