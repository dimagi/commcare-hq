from django.http import HttpResponse
from couchforms.views import post as couchforms_post

def post(request, domain):
    def callback(doc):
        doc['#export_tag'] = ["domain", "xmlns"]
        doc['submit_ip'] = request.META['REMOTE_ADDR']
        doc['domain'] = domain
        doc.save()
        return HttpResponse("Success! Received XForm id is: %s\n" % doc['_id'])
    return couchforms_post(request, callback)
