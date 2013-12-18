from datetime import datetime
import logging
from dimagi.utils.web import get_ip
from django.http import HttpResponse, HttpResponseServerError
from couchforms.models import XFormInstance, SubmissionErrorLog
from couchforms import util as couchforms_util
from receiver.signals import successful_form_received, ReceiverResult, form_received
from django.views.decorators.http import require_POST
from django.contrib.sites.models import Site
from django.views.decorators.csrf import csrf_exempt
from receiver import xml
from django.conf import settings
from django.shortcuts import render_to_response
from django.template.context import RequestContext
from dimagi.utils.couch.database import get_db
from dimagi.utils.parsing import string_to_datetime
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


def get_received_on(request):
    received_on = request.META.get('HTTP_X_SUBMIT_TIME')
    if received_on:
        return string_to_datetime(received_on)
    else:
        return None


def get_date_header(request):
    date_header = request.META.get('HTTP_DATE')
    if date_header:
        # comes in as:
        # Mon, 11 Apr 2011 18:24:43 GMT
        # goes out as:
        # 2011-04-11T18:24:43Z
        try:
            date = datetime.strptime(date_header, "%a, %d %b %Y %H:%M:%S GMT")
            date = datetime.strftime(date, "%Y-%m-%dT%H:%M:%SZ")
        except:
            logging.error((
                "Receiver app: incoming submission has a date header "
                "that we can't parse: '%s'"
            ) % date_header)
            date = date_header
        date_header = date
    else:
        date_header = None
    return date_header


class SubmissionPost(couchforms_util.SubmissionPost):

    def __init__(self, request=None, instance=None, attachments=None,
                 auth_context=None, path=None,
                 location=None, submit_ip=None, openrosa_headers=None,
                 last_sync_token=None, received_on=None, date_header=None):
        """
        you can either pass in request or give explicit values for
        instance and attachments (defaults to {})

        (all other values are optional and used for metadata)
        if you pass in all required values explicitly, request can be omitted

        """
        self.location = location or \
            get_location(request.is_secure() if request else None)

        self.received_on = received_on or \
            (get_received_on(request) if request else None)

        self.date_header = date_header or \
            (get_date_header(request) if request else None)

        self.submit_ip = submit_ip or (get_ip(request) if request else None)

        self.last_sync_token = last_sync_token or \
            getattr(request, 'last_sync_token', None)

        self.openrosa_headers = openrosa_headers or \
            getattr(request, 'openrosa_headers', None)

        super(SubmissionPost, self).__init__(request, auth_context=auth_context,
                                             path=path, instance=instance,
                                             attachments=attachments)

    def _attach_shared_props(self, doc):
        # attaches shared properties of the request to the document.
        # used on forms and errors
        doc['submit_ip'] = self.submit_ip
        doc['path'] = self.path

        if self.openrosa_headers:
            doc['openrosa_headers'] = self.openrosa_headers

        if self.last_sync_token:
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
    return SubmissionPost(request).get_response()


def get_location(is_secure=None):
    # this is necessary, because www.commcarehq.org always uses https,
    # but is behind a proxy that won't necessarily look like https
    if hasattr(settings, "OVERRIDE_LOCATION"):
        return settings.OVERRIDE_LOCATION
    if is_secure is None:
        prefix = getattr(settings, 'DEFAULT_PROTOCOL', 'http')
    else:
        prefix = "https" if is_secure else "http"
    return "%s://%s" % (prefix, Site.objects.get_current().domain)
