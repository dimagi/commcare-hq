from __future__ import absolute_import
import logging
from django.db.models.signals import post_save
from corehq.apps.users.models import CommCareUser, CouchUser

import corehq.apps.users.xml as xml
from receiver.signals import successful_form_received, ReceiverResult, Certainty


# Signal that syncs django_user => couch_user
post_save.connect(CouchUser.django_user_post_save_signal, CouchUser)


"""
This section automatically creates Couch users whenever a registration xform is received

Question: is it possible to receive registration data from the phone after Case 3?
If so, we need to check for a user created via Case 3 and link them to this account
automatically
"""

REGISTRATION_XMLNS = "http://openrosa.org/user-registration"

def create_user_from_commcare_registration(sender, xform, **kwargs):
    """
    # this comes in as xml that looks like:
    # <n0:registration xmlns:n0="openrosa.org/user-registration">
    # <username>user</username>
    # <password>pw</password>
    # <uuid>MTBZJTDO3SCT2ONXAQ88WM0CH</uuid>
    # <date>2008-01-07</date>
    # <registering_phone_id>NRPHIOUSVEA215AJL8FFKGTVR</registering_phone_id>
    # <user_data> ... some custom stuff </user_data>
    """
    if xform.xmlns != REGISTRATION_XMLNS:
        return False
    try:
        couch_user = CommCareUser.create_from_xform(xform)
    except Exception, e:
        #import traceback, sys
        #exc_type, exc_value, exc_traceback = sys.exc_info()
        #traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        logging.exception(e)
        raise
    return ReceiverResult(xml.get_response(couch_user), Certainty.CERTAIN)

successful_form_received.connect(create_user_from_commcare_registration)