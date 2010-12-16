import logging
from django.http import HttpResponse
from dimagi.utils.logging import log_exception
from couchforms.views import post as couchforms_post
from corehq.apps.receiver.signals import post_received

def post(request, domain):
    def callback(doc):
        doc['#export_tag'] = ["domain", "xmlns"]
        doc['submit_ip'] = request.META['REMOTE_ADDR']
        doc['domain'] = domain
        doc.save()
        feedback = post_received.send_robust(sender="receiver", xform=doc)
        for func, errors in feedback:
            if errors:
                logging.error("Receiver app: problem sending post-save signal %s for xform %s" \
                              % (func, doc._id))
                log_exception(errors)
        return HttpResponse("Success! Received XForm id is: %s\n" % doc['_id'])
    return couchforms_post(request, callback)
