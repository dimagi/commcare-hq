import logging
from django.http import HttpResponse, HttpResponseServerError
import couchforms
from couchforms.models import SubmissionErrorLog
from receiver.signals import successful_form_received, ReceiverResult
from receiver import xml
from receiver.xml import ResponseNature
from couchforms.signals import submission_error_received


class SubmissionPost(couchforms.SubmissionPost):

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
                xml.get_simple_response_xml("Thanks for submitting!",
                                            ResponseNature.SUBMIT_SUCCESS),
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

    def get_success_response(self, instance):
        if instance.doc_type == "XFormInstance":
            response = self.success_actions_and_respond(instance)
        else:
            response = self.fail_actions_and_respond(instance)

        # this hack is required for ODK
        response["Location"] = self.location

        # this is a magic thing that we add
        response['X-CommCareHQ-FormID'] = instance.get_id
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
