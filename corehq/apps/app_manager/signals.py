from datetime import timedelta
from couchdbkit.exceptions import MultipleResultsFound
from corehq.apps.app_manager.models import Application, get_app
from corehq.apps.app_manager.success_message import SuccessMessage
from receiver.signals import successful_form_received, Certainty, ReceiverResult
from receiver import xml
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
        try:
            app = Application.get_by_xmlns(domain, xmlns)
        except MultipleResultsFound:
            try:
                app = get_app(domain, xform.app_id)
            except Exception:
                app = None
            

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
                return ReceiverResult(xml.get_simple_response_xml(success_message), Certainty.STRONG)

successful_form_received.connect(get_custom_response_message)