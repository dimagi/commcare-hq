import logging
from django.http import HttpResponse, HttpResponseServerError
import couchforms
from couchforms.models import XFormInstance, SubmissionErrorLog
import receiver
from receiver.signals import successful_form_received, ReceiverResult, form_received
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
from receiver import xml
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from dimagi.utils.couch.database import get_db
from receiver.xml import ResponseNature
from couchforms.signals import submission_error_received


def home(request):
    forms = get_db().view('couchforms/by_xmlns', group=True, group_level=1)
    forms = dict([(x['key'], x['value']) for x in forms])
    return render_to_response("receiver/home.html", {"forms": forms}, RequestContext(request))
    

def form_list(request):
    """
    Serve forms for ODK. 
    """
    # based off: https://github.com/dimagi/data-hq/blob/moz/datahq/apps/receiver/views.py
    # TODO: serve our forms here
    # forms = get_db().view('exports_forms/by_xmlns', startkey=[domain], endkey=[domain, {}], group=True)
    
    # NOTE: THIS VIEW/METHOD DOES NOTHING CURRENTLY!!
    xml = "<forms>\n"
    forms = []
    for form in forms:
        xml += '\t<form url="%(url)s">%(name)s</form>\n' % {"url": form.url, "name": form.name}
    xml += "</forms>"
    return HttpResponse(xml, mimetype="text/xml")


class SubmissionPost(couchforms.SubmissionPost):

    def __init__(self, instance=None, attachments=None,
                 auth_context=None, path=None,
                 location=None, submit_ip=None, openrosa_headers=None,
                 last_sync_token=None, received_on=None, date_header=None):

        # get_location has good default
        self.location = location or receiver.get_location()
        self.received_on = received_on
        self.date_header = date_header
        self.submit_ip = submit_ip
        self.last_sync_token = last_sync_token
        self.openrosa_headers = openrosa_headers

        super(SubmissionPost, self).__init__(auth_context=auth_context,
                                             path=path, instance=instance,
                                             attachments=attachments)

    def _attach_shared_props(self, doc):
        # attaches shared properties of the request to the document.
        # used on forms and errors
        doc['submit_ip'] = self.submit_ip
        doc['path'] = self.path

        doc['openrosa_headers'] = self.openrosa_headers

        doc['last_sync_token'] = self.last_sync_token

        if self.received_on:
            doc.received_on = self.received_on

        if self.date_header:
            doc['date_header'] = self.date_header

        return doc

    def success_actions_and_respond(self, doc):
        feedback = successful_form_received.send_robust(sender='receiver', xform=doc)
        responses = []
        errors = []
        for func, resp in feedback:
            if resp and isinstance(resp, Exception):
                error_message = unicode(resp)
                # hack to log exception type (no valuable stacktrace though)
                try:
                    raise resp
                except Exception:
                    logging.exception((
                        u"Receiver app: problem sending "
                        u"post-save signal %s for xform %s: %s"
                    ) % (func, doc._id, error_message))
                errors.append(error_message)
            elif resp and isinstance(resp, ReceiverResult):
                responses.append(resp)

        if errors:
            # in the event of errors, respond with the errors, and mark the problem
            doc.problem = ", ".join(errors)
            doc.save()
            response = HttpResponse(
                xml.get_simple_response_xml(
                    message=doc.problem,
                    nature=ResponseNature.SUBMIT_ERROR,
                ),
                status=201,
            )
        elif responses:
            # use the response with the highest priority if we got any
            responses.sort()
            response = HttpResponse(responses[-1].response, status=201)
        else:
            # default to something generic
            response = HttpResponse(
                xml.get_simple_response_xml(
                    message="Success! Received XForm id is: %s\n" % doc['_id'],
                    nature=ResponseNature.SUBMIT_SUCCESS,
                ),
                status=201,
            )
        return response

    def fail_actions_and_respond(self, doc):
        return HttpResponse(
            xml.get_simple_response_xml(
                message=doc.problem,
                nature=ResponseNature.SUBMIT_ERROR,
            ),
            status=201,
        )

    def get_success_response(self, doc):
        # get a fresh copy of the doc, in case other things modified it.
        instance = XFormInstance.get(doc.get_id)
        self._attach_shared_props(instance)
        form_received.send(sender="receiver", xform=instance)
        instance.save()

        if instance.doc_type == "XFormInstance":
            response = self.success_actions_and_respond(instance)
        else:
            response = self.fail_actions_and_respond(instance)

        # this hack is required for ODK
        response["Location"] = self.location

        # this is a magic thing that we add
        response['X-CommCareHQ-FormID'] = doc.get_id
        return response

    def get_error_response(self, error_log):
        error_doc = SubmissionErrorLog.get(error_log.get_id)
        self._attach_shared_props(error_doc)
        submission_error_received.send(sender="receiver", xform=error_doc)
        error_doc.save()
        return HttpResponseServerError(
            xml.get_simple_response_xml(
                message="The sever got itself into big trouble! Details: %s" % error_log.problem,
                nature=ResponseNature.SUBMIT_ERROR))


@csrf_exempt
@require_POST
def post(request):
    instance, attachments = receiver.get_instance_and_attachment(request)
    return SubmissionPost(
        instance=instance,
        attachments=attachments,
        location=receiver.get_location(request),
        received_on=receiver.get_received_on(request),
        date_header=receiver.get_date_header(request),
        path=receiver.get_path(request),
        submit_ip=receiver.get_submit_ip(request),
        last_sync_token=receiver.get_last_sync_token(request),
        openrosa_headers=receiver.get_openrosa_headers(request),
    ).get_response()
