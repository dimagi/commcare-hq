from touchforms.formplayer.signals import sms_form_complete
from corehq.apps.receiverwrapper.util import get_submit_url
from receiver.util import spoof_submission

def handle_sms_form_complete(sender, session_id, form, **kwargs):
    from corehq.apps.smsforms.models import XFormsSession
    session = XFormsSession.view("smsforms/sessions_by_touchforms_id", 
                                 key=session_id, include_docs=True).one()
    if session:
        resp = spoof_submission(get_submit_url(session.domain), 
                                form, hqsubmission=False)
        xform_id = resp['X-CommCareHQ-FormID']
        session.end(completed=True)
        session.submission_id = xform_id
        session.save()
        
sms_form_complete.connect(handle_sms_form_complete)