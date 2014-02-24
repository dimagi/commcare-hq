from __future__ import absolute_import
from django.conf import settings
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
    return ReceiverResult(xml.get_simple_response_xml(
        "Thanks for submitting!", ResponseNature.SUBMIT_SUCCESS),
        Certainty.MILD)

successful_form_received.connect(send_default_response)