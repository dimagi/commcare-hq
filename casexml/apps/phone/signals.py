from __future__ import absolute_import
from receiver.signals import successful_form_received, ReceiverResult,\
    Certainty
from receiver import xml as xml
from datetime import datetime
from dimagi.utils.couch.database import get_db
from receiver.xml import ResponseNature

def send_default_response(sender, xform, **kwargs):
    """
    This signal just sends a default response to xform submissions.
    """
    
    def forms_submitted_count(user):
        forms_submitted = get_db().view("couchforms/by_user", 
                                        startkey=[user], 
                                        endkey=[user, {}]).one()
        return forms_submitted["value"] if forms_submitted else "at least 1"
    
    def forms_submitted_today_count(user):
        today = datetime.today()
        startkey = [user, today.year, today.month - 1, today.day]
        endkey = [user, today.year, today.month - 1, today.day, {}]
        forms_submitted_today = get_db().view("couchforms/by_user", 
                                              startkey=startkey, 
                                              endkey=endkey).one()
        return forms_submitted_today["value"] if forms_submitted_today else "at least 1"
        
    if xform.metadata and xform.metadata.userID:
        if xform.metadata.username == "demo_user":
            message = "Thanks for submitting from demo mode!"
        else: 
            to = ", %s" % xform.metadata.username if xform.metadata.username else ""
            message = ("Thanks for submitting%s.  We have received %s forms from "
                       "you today (%s forms all time)") % \
                       (to,
                        forms_submitted_today_count(xform.metadata.userID), 
                        forms_submitted_count(xform.metadata.userID))
        return ReceiverResult(xml.get_simple_response_xml(
            message, nature=ResponseNature.SUBMIT_SUCCESS), Certainty.MILD)
            
    else:
        return ReceiverResult(xml.get_simple_response_xml(
            "Thanks for submitting!", ResponseNature.SUBMIT_SUCCESS), 
            Certainty.MILD)


successful_form_received.connect(send_default_response)