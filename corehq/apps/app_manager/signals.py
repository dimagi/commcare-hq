from datetime import timedelta
from corehq.apps.app_manager.models import Application
from corehq.apps.app_manager.util import SuccessMessage
from corehq.apps.users.models import CouchUser
from receiver.signals import successful_form_received, Certainty, ReceiverResult

def get_success_message(sender, xform, **kwargs):
    userID = xform.form.get('meta', {}).get('userID')
    xmlns = xform.form.get('@xmlns')
    couch_user = CouchUser.view('users/by_login', key=userID, include_docs=True).one()

    app = Application.get_by_xmlns(xmlns)
    print userID, xmlns
#    return ReceiverResult(SuccessMessage(app.success_message, userID, tz=timedelta(hours=0)), Certainty.CERTAIN)


successful_form_received.connect(get_success_message)