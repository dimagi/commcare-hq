from datetime import timedelta
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.success_message import SuccessMessage
from corehq.apps.users.models import CouchUser, CommCareAccount
from receiver.signals import successful_form_received, Certainty, ReceiverResult
from casexml.apps.phone import xml

def get_success_message(sender, xform, **kwargs):
    userID = xform.form.get('meta', {}).get('userID')
    xmlns = xform.form.get('@xmlns')
    commcare_account = CommCareAccount.get_by_userID(userID)
    if not commcare_account:
        return False
    lang = "en"
    domain = commcare_account.domain
    app = Application.get_by_xmlns(domain, xmlns)
    message = app.success_message.get(lang)
    if not message:
        return False
    success_message = SuccessMessage(message, userID, tz=timedelta(hours=0)).render()
    return ReceiverResult(xml.get_response(success_message), Certainty.CERTAIN)


#successful_form_received.connect(get_success_message)