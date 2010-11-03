import logging
from django.conf import settings
from dimagi.utils.post import post_data, post_authenticated_data
from dimagi.utils.logging import log_exception
from couchforms.models import XFormInstance
from couchforms.signals import xform_saved

def post_xform_to_couch(instance):
    """
    Post an xform to couchdb, based on the settings.XFORMS_POST_URL.
    Returns the newly created document from couchdb, or raises an
    exception if anything goes wrong
    """
    # check settings for authentication credentials
    if settings.COUCH_USERNAME:
        response, errors = post_authenticated_data(instance, settings.XFORMS_POST_URL, 
                                                   settings.COUCH_USERNAME, 
                                                   settings.COUCH_PASSWORD)
    else:
        response, errors = post_data(instance, settings.XFORMS_POST_URL)
    if not errors and not "error" in response:
        doc_id = response
        try:
            xform = XFormInstance.get(doc_id)
            xform_saved.send_robust(sender="post", form=xform)
            return xform
        except Exception, e:
            logging.error("Problem accessing %s" % doc_id)
            log_exception(e)
            raise
    else:
        raise Exception("Problem POSTing form to couch! errors/response: %s/%s" % (errors, response))

def value_for_display(value, replacement_chars="_-"):
    """
    Formats an xform value for display, replacing the contents of the 
    system characters with spaces
    """
    for char in replacement_chars:
        value = str(value).replace(char, " ")
    return value