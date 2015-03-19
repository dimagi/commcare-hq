from touchforms.formplayer.signals import sms_form_complete
from corehq.apps.receiverwrapper.util import get_submit_url
from corehq.apps.receiverwrapper.util import submit_form_locally
from couchforms.models import XFormInstance

def handle_sms_form_complete(sender, session_id, form, **kwargs):
    from corehq.apps.smsforms.models import SQLXFormsSession
    session = SQLXFormsSession.by_session_id(session_id)
    if session:
        resp = submit_form_locally(form, session.domain, app_id=session.app_id)
        xform_id = resp['X-CommCareHQ-FormID']
        session.end(completed=True)
        session.submission_id = xform_id
        session.save()
        
        xform = XFormInstance.get(xform_id)
        xform.survey_incentive = session.survey_incentive
        xform.save()
        
sms_form_complete.connect(handle_sms_form_complete)
