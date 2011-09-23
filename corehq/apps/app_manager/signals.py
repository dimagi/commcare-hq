from datetime import timedelta
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.success_message import SuccessMessage
from corehq.apps.users.models import CouchUser, CommCareUser
from receiver.signals import successful_form_received, Certainty, ReceiverResult
from casexml.apps.phone import xml
from corehq.middleware import OPENROSA_ACCEPT_LANGUAGE

def get_custom_response_message(sender, xform, **kwargs):
    """
    This signal sends a custom response to xform submissions. 
    If the domain has one.
    """
    if xform.metadata and xform.metadata.userID:
        userID = xform.metadata.userID
        xmlns = xform.form.get('@xmlns')
        domain = xform.domain
        lang = xform.openrosa_headers.get(OPENROSA_ACCEPT_LANGUAGE, "en") \
                if hasattr(xform, "openrosa_headers") else "en"
        app = Application.get_by_xmlns(domain, xmlns)
        message = app.success_message.get(lang) if app else None
        if not message:
            return
        success_message = SuccessMessage(message, userID, domain=domain, tz=timedelta(hours=0)).render()
        return ReceiverResult(xml.get_response(success_message), Certainty.STRONG)

successful_form_received.connect(get_custom_response_message)