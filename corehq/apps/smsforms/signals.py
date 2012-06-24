from touchforms.formplayer.signals import sms_form_complete
from corehq.apps.receiverwrapper.util import get_submit_url
from receiver.util import spoof_submission

def handle_sms_form_complete(sender, session_id, form, **kwargs):
    from corehq.apps.smsforms.models import XFormsSession
    session = XFormsSession.latest_by_session_id(session_id)
    if session:
        # i don't know if app_id is the id of the overall app or the id of the specific build of the app
        # the thing i want to pass in is the id of the overall app
        resp = spoof_submission(get_submit_url(session.domain, session.app_id),
                                form, hqsubmission=False)
        xform_id = resp['X-CommCareHQ-FormID']
        session.end(completed=True)
        session.submission_id = xform_id
        session.save()
        
sms_form_complete.connect(handle_sms_form_complete)