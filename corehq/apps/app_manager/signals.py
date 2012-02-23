from datetime import timedelta
from couchdbkit.exceptions import MultipleResultsFound
from corehq.apps.app_manager.models import Application, get_app
from corehq.apps.app_manager.success_message import SuccessMessage
from receiver.signals import successful_form_received, Certainty, ReceiverResult
from receiver import xml
from corehq.middleware import OPENROSA_ACCEPT_LANGUAGE
from receiver.xml import ResponseNature

def get_custom_response_message(sender, xform, **kwargs):
    """
    This signal sends a custom response to xform submissions. 
    If the domain has one.
    """
    if xform.metadata and xform.metadata.userID:
        userID = xform.metadata.userID
        xmlns = xform.form.get('@xmlns')
        domain = xform.domain

        try:
            app = get_app(domain, xform.app_id)
        except Exception:
            app = Application.get_by_xmlns(domain, xmlns)

        if app and hasattr(app, 'langs'):
            try:
                lang = xform.openrosa_headers[OPENROSA_ACCEPT_LANGUAGE]
            except (AttributeError, KeyError):
                lang = "default"
            if lang == "default":
                lang = app.langs[0] if app.langs else None
            message = app.success_message.get(lang)
            if message:
                success_message = SuccessMessage(message, userID, domain=domain, tz=timedelta(hours=0)).render()
                return ReceiverResult(xml.get_simple_response_xml(
                    success_message, nature=ResponseNature.SUBMIT_SUCCESS),
                    Certainty.STRONG)

successful_form_received.connect(get_custom_response_message)