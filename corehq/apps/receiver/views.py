import logging
from django.http import HttpResponse
from corehq.apps.case.models.couch import CommCareCase
from couchforms.views import post as couchforms_post
from corehq.apps.receiver.signals import post_received, ReceiverResult
from django.views.decorators.http import require_POST
from django.contrib.sites.models import Site


@require_POST
def post(request, domain):
    def callback(doc):
        doc['#export_tag'] = ["domain", "xmlns"]
        doc['submit_ip'] = request.META['REMOTE_ADDR']
        doc['domain'] = domain

        # a hack allowing you to specify the submit time to use
        # instead of the actual time receiver
        # useful for migrating data
        received_on = request.META.get('HTTP_X_SUBMIT_TIME')
        if received_on:
            doc['received_on'] = received_on
            
        def _scrub_meta(doc):
            property_map = {"TimeStart": "timeStart",
                            "TimeEnd": "timeEnd",
                            "chw_id": "userID",
                            "DeviceID": "deviceID",
                            "uid": "instanceID"}

            # hack to make sure uppercase meta still ends up in the right place
            found_old = False
            if "Meta" in doc.form:
                doc.form["meta"] = doc.form["Meta"]
                del doc.form["Meta"]
                found_old = True
            if "meta" in doc.form:
                # scrub values from 0.9 to 1.0
                for key in doc.form["meta"]:
                    if key in property_map and property_map[key] not in doc.form["meta"]:
                        doc.form["meta"][property_map[key]] = doc.form["meta"][key]
                        del doc.form["meta"][key]
                        found_old = True
            return found_old
        if _scrub_meta(doc):
            logging.error("form %s contains old-format metadata.  You should update it!!" % doc.get_id)
        doc.save()
        feedback = post_received.send_robust(sender="receiver", xform=doc)
        responses = []
        for func, resp in feedback:
            if resp and isinstance(resp, Exception):
                logging.error("Receiver app: problem sending post-save signal %s for xform %s" \
                              % (func, doc._id))
                logging.exception(resp)
            elif resp and isinstance(resp, ReceiverResult):
                # use the first valid response if we get one
                responses.append(resp)

        # hack the domain into any case that has been created
        def case_domain_hack(xform):
            case = CommCareCase.view('case/by_xform_id', key=xform._id, include_docs=True).one()
            case.domain = xform.domain
            case.save()
        try:
            case_domain_hack(doc)
        except:
            pass

        if responses:
            responses.sort()
            response = HttpResponse(responses[-1].response, status=201)
        else:
            # default to something generic 
            response = HttpResponse("Success! Received XForm id is: %s\n" % doc['_id'], status=201)
        
        # this hack is required for ODK
        response["Location"] = "http://%s" % Site.objects.get_current().domain
        return response 
        
    return couchforms_post(request, callback)