import logging
from django.http import HttpResponse
from couchforms.views import post as couchforms_post
from corehq.apps.receiver.signals import post_received, ReceiverResult

def post(request, domain):
    def callback(doc):
        doc['#export_tag'] = ["domain", "xmlns"]
        doc['submit_ip'] = request.META['REMOTE_ADDR']
        doc['domain'] = domain
        doc.save()
        feedback = post_received.send_robust(sender="receiver", xform=doc)
        to_respond = None
        for func, resp in feedback:
            if resp and isinstance(resp, Exception):
                logging.error("Receiver app: problem sending post-save signal %s for xform %s" \
                              % (func, doc._id))
                logging.exception(resp)
            elif resp and not to_respond and isinstance(resp, ReceiverResult):
                # use the first valid response if we get one 
                to_respond = resp
        if to_respond:
            return HttpResponse(to_respond.response)
        # default to something generic
        return HttpResponse("Success! Received XForm id is: %s\n" % doc['_id'])
    return couchforms_post(request, callback)
