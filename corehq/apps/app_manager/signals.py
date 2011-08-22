from datetime import timedelta
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.success_message import SuccessMessage
from corehq.apps.users.models import CouchUser, CommCareAccount
from receiver.signals import successful_form_received, Certainty, ReceiverResult
from casexml.apps.phone import xml

def get_custom_response_message(sender, xform, **kwargs):
    """
    This signal sends a custom response to xform submissions. 
    If the domain has one.
    """
    if xform.metadata and xform.metadata.userID:
        userID = xform.metadata.userID
        xmlns = xform.form.get('@xmlns')
        commcare_account = CommCareAccount.get_by_userID(userID)
        if not commcare_account:
            return False
        lang = "en"
        domain = commcare_account.domain
        app = Application.get_by_xmlns(domain, xmlns)
        message = app.success_message.get(lang) if app else None
        if not message:
            return 
        success_message = SuccessMessage(message, userID, tz=timedelta(hours=0)).render()
        return ReceiverResult(xml.get_response(success_message), Certainty.STRONG)

successful_form_received.connect(get_custom_response_message)