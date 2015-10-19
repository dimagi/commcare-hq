from touchforms.formplayer.signals import sms_form_complete
from corehq.apps.receiverwrapper.util import submit_form_locally
from couchforms.models import XFormInstance


def handle_sms_form_complete(sender, session_id, form, **kwargs):
    from corehq.apps.smsforms.models import SQLXFormsSession
    session = SQLXFormsSession.by_session_id(session_id)
    if session:
        resp, xform, cases = submit_form_locally(form, session.domain, app_id=session.app_id)
        session.end(completed=True)
        session.submission_id = xform.get_id
        session.save()

        xform.survey_incentive = session.survey_incentive
        xform.save()

sms_form_complete.connect(handle_sms_form_complete)
